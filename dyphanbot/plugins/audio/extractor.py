import re
import asyncio
import datetime
from functools import partial

import discord
from dyphanbot import PluginError

import youtube_dl

YTDL_OPTS = {
    'format': 'webm[abr>0]/bestaudio/best',
    'prefer_ffmpeg': True,
    'ignoreerrors': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class AudioExtractionError(PluginError):
    """ Raised when YTDLExtractor errors """
    def __init__(self, message, display_message=None):
        super().__init__(message)
        self.display_message = display_message
        if not display_message:
            self.display_message = message


class YTDLExtractor(object):
    """ Handles youtube-dl extraction """

    def __init__(self, loop=None):
        self._tasks = []
        self.loop = loop or asyncio.get_event_loop()

        self.ytdl = youtube_dl.YoutubeDL(YTDL_OPTS)

        # monkey patch ytdl's exception handler so we can catch our own
        if self.ytdl.__class__._YoutubeDL__extract_info.__closure__:
            self.ytdl.__class__._YoutubeDL__extract_info = youtube_dl.YoutubeDL._YoutubeDL__extract_info.__closure__[0].cell_contents

    def _future_callback(self, future):
        # ignore cancelled errors
        try:
            future.exception()
        except asyncio.CancelledError:
            pass
    
    async def _run_future(self, func):
        future = self.loop.run_in_executor(None, func)
        future.add_done_callback(self._future_callback)
        self._tasks.append(future)
        return await future
    
    async def extract_info(self, **kwargs):
        to_run = partial(self.ytdl.extract_info, **kwargs)
        return await self._run_future(to_run)
    
    async def _process_data(self, data, depth=0):
        # Processes the data until data['_type'] is either 'video' or 'playlist'
        # This references a portion of youtube-dl's own code, except it only
        # handles 'url' or 'url_transparent' result types since we do playlist
        # and video processing later on.
        # This method shouldn't be called on playlist entries!
        result_type = data.get('_type', 'video')

        if result_type in ('url', 'url_transparent'):
            data['url'] = youtube_dl.utils.sanitize_url(data['url'])
        
        if result_type == 'url':
            return await self.extract_info(
                url=data['url'], ie_key=data.get('ie_key'),
                download=False, process=False)
        elif result_type == 'url_transparent':
            info = await self.extract_info(
                url=data['url'], ie_key=data.get('ie_key'),
                download=False, process=False)

            if not info:
                return info
            
            fprops = {(k, v) for k, v in data.items() if v is not None}
            for f in ('_type', 'url', 'id', 'extractor', 'extractor_key', 'ie_key'):
                if f in fprops:
                    del fprops[f]
            new_data = info.copy()
            new_data.update(fprops)

            if new_data.get('_type') == 'url':
                new_data['_type'] = 'url_transparent'
            
            if depth <= 3:
                return await self._process_data(new_data, depth+1)
            return new_data # we've gone too deep...
        else:
            return data
    
    async def _generate_playlist_data(self, data: dict, message_callback=None):
        if not 'entries' in data:
            return None
        new_data = {
            '_type': 'playlist',
            'id': data.get('id', "custom-playlist"),
            'title': data.get('title', "Untitled Custom Playlist"),
            'entries': []
        }

        for entry in data['entries']:
            if 'url' in entry:
                try:
                    entry_info = await self.extract_info(
                        url=entry['url'], download=False, process=False)
                    if entry_info.get('_type') == 'playlist':
                        # too much hassle in handling playlists inside of each other
                        continue
                    if 'data' in entry:
                        entry_info.update(entry['data'])
                    entry_info['_custom_playlist'] = True
                    new_data['entries'].append(entry_info)
                except youtube_dl.utils.YoutubeDLError:
                    if message_callback:
                        await message_callback(
                            content="Skipped `{}` due to an error.".format(
                            entry.get('data', {}).get('title', entry['url']))
                        )
                    continue
            elif 'id' in entry:
                entry_info = {}
                entry_info['id'] = entry['id']
                if 'data' in entry:
                    entry_info.update(entry['data'])
                new_data['entries'].append(entry_info)
        
        return new_data
    
    async def extract_video_data(self, query):
        data = await self.extract_info(url=query, download=False, process=False)
        
        # Process the result till we get a playlist or a video
        return await self._process_data(data)
    
    async def process_entries(self, search, *, custom_data={},
                              channel=None, requester=None,
                              message_callback=None):
        if isinstance(search, dict):
            data = await self._generate_playlist_data(search, message_callback)
            if not data:
                raise AudioExtractionError(
                    "Custom playlist data missing required values.",
                    "Unable to generate playlist... :c"
                )
            if not data['entries']:
                raise AudioExtractionError(
                    "Custom playlist is empty.",
                    "The playlist is empty... :c"
                )
        else:
            try:
                data = await self.extract_video_data(search)
            except youtube_dl.utils.UnsupportedError as err:
                raise AudioExtractionError(
                    str(err),
                    "URL is not supported! Dx"
                )
            except youtube_dl.utils.YoutubeDLError as err:
                err_msg = str(err)

                # remove mentions of "Sign in" to avoid confusion
                err_msg = re.sub(".*sign in.*\n?", "", err_msg, flags=re.I|re.M).strip()

                msg = "Unable to retrieve content... :c"
                if "Unable to download webpage:" not in err_msg:
                    msg += "\n```{}```".format(err_msg)
                
                if "Unable to extract" in err_msg:
                    msg = "Unable to extract content... :c"
                
                if ("name resolution" in err_msg.lower() or
                    "no address" in err_msg.lower() or
                    "service not known" in err_msg.lower()):
                    msg = ("Site not found! Dx\n"
                           "Make sure that the site exists and that you typed "
                           "the URL or query correctly.")
                
                raise AudioExtractionError(
                    str(err),
                    msg
                )
            except Exception as err:
                raise AudioExtractionError(
                    str(err),
                    "Unable to request content... x_x\n"
                    "Make sure you typed the URL or query correctly."
                )
        
        if 'entries' in data:
            # a playlist; put it in YTDLPlaylist to process later
            return YTDLPlaylist(self, data, channel, requester, custom_data)
        else:
            # Not a playlist, so the entry data is in `data`
            return YTDLEntry(self, data, channel, requester, custom_data)
    
    def cleanup(self):
        for task in self._tasks:
            task.cancel()


class YTDLObject(object):
    def __init__(self, ytdl_extractor: YTDLExtractor):
        self.ytdl_extractor = ytdl_extractor
        self.ytdl = self.ytdl_extractor.ytdl

class YTDLPlaylist(YTDLObject):

    def __init__(self, ytdl_extractor: YTDLExtractor, data: dict,
                 channel: discord.TextChannel, requester: discord.Member,
                 custom_data={}):
        super().__init__(ytdl_extractor)
        self.channel = channel
        self.requester = requester

        self._data = data
        self._custom_data = custom_data
        self._entries = data.get('entries')
        self.id = data.get('id')
        self.title = data.get('title')
        self.uploader = data.get('uploader')
        self.uploader_id = data.get('uploader_id')
        self.web_url = data.get('webpage_url')
        self.extractor = data.get('extractor')
        self.extractor_key = data.get('extractor_key')
    
    def _get_video_id_from_url(self):
        # a 'hacky' way to get videos with playlists to start from the current
        # video instead of the beginning of the playlist
        if not self.web_url:
            return None
        video_opts = {'noplaylist':True, 'ignoreerrors':True}
        video_info = youtube_dl.YoutubeDL(video_opts).extract_info(
            url=self.web_url,
            download=False,
            process=False)
        if not video_info or 'playlist' in video_info.get('_type', '') or video_info.get('id') == self.id:
            return None # url is actually a playlist instead of a video in a playlist
        return video_info.get('id')
    
    def entries(self):
        """ Generates a list of YTDLPlaylistEntry objects to be processed later """
        entries = []
        found = False
        try:
            v_id = self._get_video_id_from_url()
            for i, entry in enumerate(self._entries, 1):
                if v_id and v_id != entry.get('id') and not found:
                    continue # skip till we get to the current id
                found = True # we found the video, stop skipping and add the rest
                playlist_entry = YTDLPlaylistEntry(self.ytdl_extractor, self,
                    entry, self.channel, self.requester, index=i)
                entries.append(playlist_entry)
        except youtube_dl.utils.YoutubeDLError as err:
            raise AudioExtractionError(
                    str(err),
                    "Unable to retrieve content... :c"
                )
        return entries

class YTDLPlaylistEntry(YTDLObject):
    """ Represents an unprocessed playlist entry """
    def __init__(self, ytdl_extractor: YTDLExtractor, playlist: YTDLPlaylist,
                 data: dict, channel: discord.TextChannel,
                 requester: discord.Member, index=0, custom_data={}):
        print(ytdl_extractor)
        super().__init__(ytdl_extractor)
        self._data = data
        self._custom_data = custom_data
        self.id = data.get('id')
        self.title = data.get('title', "*N/A*") or "*Untitled*"
        self.playlist = playlist
        self.playlist_index = index
        self.requester = requester
        self.channel = channel
    
    async def process(self):
        """ Processes this playlist entry into a YTDLEntry """
        if 'on_process' in self._data:
            data = self._data['on_process']()
            if data.get('_complete'):
                return YTDLEntry(self.ytdl_extractor, data, self.channel, self.requester)
            self._data.update(data)
        weburl_base = None
        if self.playlist.web_url:
            weburl_base = youtube_dl.utils.url_basename(self.playlist.web_url)
        extra_info = {
            'playlist': self.playlist._data,
            'playlist_id': self.playlist.id,
            'playlist_title': self.playlist.title,
            'playlist_uploader': self.playlist.uploader,
            'playlist_uploader_id': self.playlist.uploader_id,
            'playlist_index': self.playlist_index,
            'webpage_url': self.playlist.web_url,
            'webpage_url_basename': weburl_base,
            'extractor': self.playlist.extractor,
            'extractor_key': self.playlist.extractor_key,
        }

        try:
            to_run = partial(
                self.ytdl.process_ie_result,
                ie_result=self._data,
                download=False,
                extra_info={k: v for k, v in extra_info.items() if v}
            )
            entry_result = await self.ytdl_extractor._run_future(to_run)
            if not entry_result:
                return None
        except Exception as e:
            if self.channel:
                await self.channel.send(
                    "There was an error processing your requested audio source."
                    "```py\n{}: {}\n```".format(type(e).__name__, e))
            raise
        else:
            return YTDLEntry(self.ytdl_extractor, entry_result, self.channel,
                         self.requester, self._custom_data)

class YTDLEntry(YTDLObject):
    """ Represents a youtube-dl entry """
    def __init__(self, ytdl_extractor: YTDLExtractor, data: dict,
                 channel: discord.TextChannel, requester: discord.Member,
                 custom_data={}):
        super().__init__(ytdl_extractor)
        self.channel = channel
        self.requester = requester

        self._data = data
        self._custom_data = custom_data
        self._update_data(data, custom_data)
    
    def _update_data(self, data: dict, custom_data={}):
        data.update(custom_data)
        self._data = data
        self.id = data.get('id')
        self.title = data.get('title', "*No Title*") or "*Untitled*"
        self.description = data.get('description', "")
        self.web_url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.is_live = bool(data.get('is_live'))
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.duration = data.get('duration')
        self.uploader = data.get('uploader')
        self.thumbnail = data.get('thumbnail')

        # upload date handling
        date = data.get('upload_date')
        if date:
            try:
                date = datetime.datetime.strptime(date, '%Y%M%d').date()
            except ValueError:
                date = None

        self.upload_date = date
    
    def create_source(self):
        """ Generates a playable source from the entry data """
        return YTDLSource(discord.FFmpegPCMAudio(self.ytdl.prepare_filename(self._data), **FFMPEG_OPTS), entry=self)
    
    async def regather_source(self):
        if 'on_regather' in self._data:
            regathered_data = self._data['on_regather']()
            self._update_data(self._data, regathered_data)
            return YTDLSource(discord.FFmpegPCMAudio(self._data['url'], **FFMPEG_OPTS), entry=self)
        regathered_data = await self.ytdl_extractor.extract_info(url=self.web_url, download=False)
        if self._data.get('_custom_playlist'):
            self._custom_data = self._data
        regathered_data.update(self._custom_data)
        self._update_data(self._data, regathered_data)
        return YTDLSource(discord.FFmpegPCMAudio(self._data['url'], **FFMPEG_OPTS), entry=self)

class YTDLSource(discord.PCMVolumeTransformer):
    """ Playable source object for YTDL """
    def __init__(self, source, *, entry: YTDLEntry, progress: float=0):
        super().__init__(source)
        self.entry = entry
        self.requester = entry.requester
        self.progress = progress

        # get these attributes from the entry (pls tell me there's a better way...)
        for attr in ['title', 'description', 'web_url', 'views', 'is_live',
                     'likes', 'dislikes', 'duration', 'uploader', 'thumbnail',
                     'upload_date']:
            setattr(self, attr, getattr(self.entry, attr))
    
    def read(self):
        ret = super().read()
        if ret:
            self.progress += 1
        return ret
    
    def get_progress(self):
        return self.progress * 0.02
