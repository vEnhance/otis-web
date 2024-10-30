"""Finds hidden diamonds in raw plaintext"""

import os
import io
import pathlib
import warnings
from collections import defaultdict


class DiamondFinder(defaultdict):
    def __init__(self, chars, minlen, maxlen, notify_diamonds=False):
        self.chars = chars
        self.minlen = minlen
        self.maxlen = maxlen
        self.notify_diamonds = notify_diamonds
        super().__init__(list)

    def __repr__(self):
        return f'{__class__.__name__}({super(defaultdict, self).__repr__()})'

    def __str__(self):
        return '\n'.join(self.keys())

    def scan(self, source=None, tag=None):
        if source is None:
            return
        if tag is None:
            tag = ()
        elif not isinstance(tag, tuple):
            tag = (tag,)
        if isinstance(source, str):
            self.scantext(source, tag)
        elif isinstance(source, io.TextIOBase):
            self.scanstream(source, tag)

    def scantext(self, text, tag=()):
        lines = text.split('\n')
        for count, line in enumerate(lines, 1):
            linetag = tag + (count,)
            self.scanline(line + '\n', linetag)

    def scandir(self, directory, deep=False, tag=(), **kwargs):
        dirtag = tag + (directory,)
        if deep:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    self.scanfile(
                        os.path.join(root, file),
                        relpath=directory,
                        tag=dirtag,
                        **kwargs
                    )
        else:
            for file in os.listdir(directory):
                fullpath = os.path.join(directory, file)
                if os.path.isfile(fullpath):
                    self.scanfile(
                        fullpath,
                        relpath=directory,
                        tag=dirtag,
                        **kwargs
                    )

    def scanfile(self, file, include=None, exclude=None, relpath=None, tag=()):
        if not self.check_extension(file, include, exclude):
            return
        filetag = file if relpath is None else os.path.relpath(file, relpath)
        tag = tag + (filetag,)
        with open(file, mode='r', encoding='utf-8') as stream:
            self.scanstream(stream, tag)

    @staticmethod
    def check_extension(file, include=None, exclude=None):
        extension = pathlib.Path(file).suffix
        if include is not None:
            if isinstance(include, str):
                include = [include]
            if extension in include:
                return False
        if exclude is not None:
            if isinstance(exclude, str):
                exclude = [exclude]
            if extension in exclude:
                return False
        return True

    def scanstream(self, stream, tag=()):
        count = 1
        while True:
            try:
                line = stream.readline()
            except UnicodeDecodeError:
                warnings.warn(
                    f'Failed to decode line {count} of {tag}',
                    UnicodeWarning
                )
            else:
                if not line:
                    break
                linetag = tag + (count,)
                self.scanline(line, linetag)
            finally:
                count += 1

    def scanline(self, line, tag=()):
        diamond_array = bytearray(self.maxlen)
        index = 0
        for char in line:
            if char in self.chars:
                if index >= self.maxlen:
                    continue
                diamond_array[index] = ord(char)
                index += 1
            else:
                if (self.minlen <= index <= self.maxlen):
                    diamond = diamond_array[:index].decode('utf-8')
                    self.add_diamond(diamond, tag)
                index = 0

    def add_diamond(self, diamond, tag=()):
        if self.notify_diamonds:
            print(diamond, tag)
        self[diamond].append(tag)

# Main function for scanning diamonds when running this file directly
def main():
    # Configure the DiamondFinder parameters
    chars = '0123456789abcdef'
    minlen = 24
    maxlen = 26
    notify_diamonds = True

    # Instantiate DiamondFinder
    finder = DiamondFinder(chars, minlen, maxlen, notify_diamonds)

    # Directory to scan - update as needed
    directory = 'path/to/your/directory'
    
    # Start scanning the directory
    print(f"Scanning directory: {directory}")
    finder.scandir(directory, deep=True, exclude='.lock')
    
    # Print results
    print("Diamonds found:")
    print(finder)

# Run the main function if this script is executed directly
if __name__ == "__main__":
    main()


"""
>>> os.chdir('blah/blah/blah/') # contains otis-web
>>> otis_df.scandir('otis-web/', deep=True, exclude='.lock')
...
>>> print(otis_df)
I got 4 legitimate diamonds and 14 charisma points doing this.
"""
