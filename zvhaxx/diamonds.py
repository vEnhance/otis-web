"""Finds hidden diamonds in raw plaintext"""

import io
from collections import defaultdict


class DiamondFinder(defaultdict):
    DIAMOND_CHARS = "0123456789abcdef"
    DIAMOND_LEN_MIN = 24
    DIAMOND_LEN_MAX = 26
    
    def __init__(self, dict=None, stdin=None, source=None):
      super().__init__([], dict)
      self.scan(stdin, source)

    def scan(self, stdin=None, source=None):
        if stdin is None:
            return
        if source is None:
            source = ()
        if isinstance(stdin, str):
            self.scantext(stdin, source)
        elif isinstance(stdin, io.TextIOBase):
            self.scantextfile(stdin, source)
