import os
import logging
import pathlib
import argparse

from dyphanbot.dyphanbot import DyphanBot

def main(args):
    dyphanbot = DyphanBot(**args)
    dyphanbot.run()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="shows debug log messages",
                        action="store_true")
    parser.add_argument("-d", "--dev-mode", help="halt when plugin exception occurs",
                        action="store_true")
    parser.add_argument("-c", "--config", dest="config_path", type=pathlib.Path,
                        help="path to config file (will search default paths if not specified)")
    args = vars(parser.parse_args())
    main(args)
