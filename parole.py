#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

class dizionario():
    def __init__(self, filename = 'it.txt'):
        with open(filename) as file:
            lines = file.readlines()
        self._parole = [line.rstrip().upper() for line in lines if line[0] != '#']
        
    @property
    def parole(self):
        return self._parole
        
    def anagrammi(self, parola: str, minl=None, maxl=None):
        chars = ''.join(set(parola)).upper()
        mi = '%i' % minl if minl is not None else ''
        ma = '%i' % maxl if maxl is not None else ''
                
        regexp = '^[%s]{%s,%s}$' % (re.escape(chars), mi, ma)
        r = re.compile(regexp)
        
        return [ p for p in self._parole if r.match(p) ]


if __name__ == "__main__":
    from random import sample, choice

    d = dizionario()

    print('caricate %i parole' % len(d.parole))

    a = d.anagrammi('etani',maxl=10)
    
    print('10 anagrammi su %i di etani' % len(a)) 
    print(sample(a, 10))

