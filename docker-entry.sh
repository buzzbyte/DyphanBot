#!/bin/bash

# only run at first start
if [ ! -f /.initialized ]; then
    echo "Installing plugin dependencies..."
    for f in /dyphan/.dyphan/plugins/*; do
        if [ -d "$f" ]; then
            if [ -f "$f/requirements.txt" ]; then
                pip3 install -r $f/requirements.txt;
            fi;
        fi;
    done
    touch /.initialized
fi

# Run dyphanbot
python3 -m dyphanbot