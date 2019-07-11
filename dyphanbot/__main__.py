import os
import logging
import argparse

from dyphanbot.dyphanbot import DyphanBot

def main(debug=False):
    dyphanbot = DyphanBot(debug=debug)
    dyphanbot.run()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="shows debug log messages",
                        action="store_true")
    args = parser.parse_args()
    main(args.verbose)
