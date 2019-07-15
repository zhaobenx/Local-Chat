# -*- coding: utf-8 -*-
"""
Created on 2019-07-16 00:30:30
@Author: ZHAO Lingfeng
@Version : 0.0.1
"""

def main():
    pass


if __name__ == "__main__":
    main()

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion


class MyCustomCompleter(Completer):

    def __init__(self, uuid, name_dict):
        super().__init__()
        self.name_dict = name_dict
        self.uuid = uuid

    def get_completions(self, document, complete_event):

        word_before_cursor = document.get_word_before_cursor(False)
        uuid = self.uuid

        def word_matches(word):
            """ True when the word before the cursor matches. """
            return word.startswith(word_before_cursor)

        for a in uuid:
            if word_matches(a):
                display_meta = self.name_dict.get(a, '')
                if display_meta:
                    display_meta = f'({display_meta})'
                yield Completion(a, -len(word_before_cursor), display_meta=display_meta, style='fg:ansiblue')

        for k, v in self.name_dict.items():
            if word_matches(v):

                display_meta = self.name_dict.get(k, '')
                yield Completion(k, -len(word_before_cursor), display_meta=f'({v})', style='fg:ansiblue')
