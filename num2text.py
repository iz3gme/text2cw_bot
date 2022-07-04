#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# script di traduzione di numeri in lettere
# nella lingua italiana
# traduce un numero in lettere


from decimal import Decimal
import re
 
# funzione ricorsiva
def NumberToTextInteger(n):
    if n == 0: 
        return ""
         
    elif n <= 19:
        return ("uno", "due", "tre", "quattro", "cinque", 
                "sei", "sette", "otto", "nove", "dieci", 
                "undici", "dodici", "tredici", 
                "quattordici", "quindici", "sedici", 
                "diciassette", "diciotto", "diciannove")[int(n-1)]
                 
    elif n <= 99:
        decine = ("venti", "trenta", "quaranta",
                  "cinquanta", "sessanta", 
                  "settanta", "ottanta", "novanta")
        letter = decine[int(n/10)-2]
        t = n%10
        if t == 1 or t == 8:
            letter = letter[:-1]
        return letter + NumberToTextInteger(n%10)
         
    elif n <= 199:
        return "cento" + NumberToTextInteger(n%100)
         
    elif n <= 999:
        m = n%100
        m = int(m/10)
        letter = "cent"
        if m != 8:
            letter = letter + "o"
        return NumberToTextInteger( int(n/100)) + \
               letter + \
               NumberToTextInteger(n%100)
         
    elif n<= 1999 :
        return "mille" + NumberToTextInteger(n%1000)
     
    elif n<= 999999:
        return NumberToTextInteger(int(n/1000)) + \
               "mila" + \
               NumberToTextInteger(n%1000)
         
    elif n <= 1999999:
        return "unmilione" + NumberToTextInteger(n%1000000)
         
    elif n <= 999999999:
        return NumberToTextInteger(int(n/1000000))+ \
               "milioni" + \
               NumberToTextInteger(n%1000000)
    elif n <= 1999999999:
        return "unmiliardo" + NumberToTextInteger(n%1000000000)
         
    else:
        return NumberToTextInteger(int(n/1000000000)) + \
               "miliardi" + \
               NumberToTextInteger(n%1000000000)
 
# funzione wrapper
def NumberToText(x):
   """
   Ritorna un numero tradotto in lettere
       
   >>> NumberToText('0')
   'zero'
   >>> NumberToText('-0')
   'zero'
   >>> NumberToText('1')
   'uno'
   >>> NumberToText('-1')
   'menouno'
   >>> NumberToText('2')
   'due'
   >>> NumberToText('3')
   'tre'
   >>> NumberToText('4')
   'quattro'
   >>> NumberToText('5')
   'cinque'
   >>> NumberToText('6')
   'sei'
   >>> NumberToText('7')
   'sette'
   >>> NumberToText('8')
   'otto'
   >>> NumberToText('9')
   'nove'
   >>> NumberToText('10')
   'dieci'
   >>> NumberToText('11')
   'undici'
   >>> NumberToText('12')
   'dodici'
   >>> NumberToText('13')
   'tredici'
   >>> NumberToText('14')
   'quattordici'
   >>> NumberToText('15')
   'quindici'
   >>> NumberToText('16')
   'sedici'
   >>> NumberToText('17')
   'diciassette'
   >>> NumberToText('18')
   'diciotto'
   >>> NumberToText('19')
   'diciannove'
   >>> NumberToText('20')
   'venti'
   >>> NumberToText('21')
   'ventuno'
   >>> NumberToText('22')
   'ventidue'
   >>> NumberToText('30')
   'trenta'
   >>> NumberToText('40')
   'quaranta'
   >>> NumberToText('50')
   'cinquanta'
   >>> NumberToText('60')
   'sessanta'
   >>> NumberToText('70')
   'settanta'
   >>> NumberToText('80')
   'ottanta'
   >>> NumberToText('90')
   'novanta'
   >>> NumberToText('100')
   'cento'
   >>> NumberToText('101')
   'centouno'
   >>> NumberToText('110')
   'centodieci'
   >>> NumberToText('127')
   'centoventisette'
   >>> NumberToText('200')
   'duecento'
   >>> NumberToText('599')
   'cinquecentonovantanove'
   >>> NumberToText('1000')
   'mille'
   >>> NumberToText('2000')
   'duemila'
   >>> NumberToText('127428')
   'centoventisettemilaquattrocentoventotto'
   >>> NumberToText('127,428')
   'centoventisette,quattrocentoventotto'
   >>> NumberToText('127.428')
   'centoventisettemilaquattrocentoventotto'
   >>> NumberToText('127.428,7891')
   'centoventisettemilaquattrocentoventotto,settemilaottocentonovantuno'
   >>> NumberToText('127428,7891')
   'centoventisettemilaquattrocentoventotto,settemilaottocentonovantuno'
   >>> NumberToText('1,1')
   'uno,uno'
   >>> NumberToText('127.428,69')
   'centoventisettemilaquattrocentoventotto,sessantanove'
   """
   
   # convert parameter from string to numeric if needed
   if isinstance(x, str):
       # remove any .
       x = x.replace('.','')
       # convert , to .
       x = x.replace(',','.')
       try:
           x = Decimal(x)
       except ValueError:
           return('NaN')
       
   sign = ""
   if x<0:
      sign = "meno"
      x = abs(x)
   n = int(x)

   #isolate decimal digits
   frmt = "{0:.15f}"
   spic = Decimal('0'+frmt.format(x-n)[2:].rstrip('0'))
      
   if n == 0:
      num = "zero"
   else:
      num = NumberToTextInteger(n)
      
   if spic == 0:
       return sign+num
   else:
       return sign+num+","+NumberToTextInteger(spic)


def FindNumbers(text):
    """
    return a generator for all (start, stop, substr) tuples of numeric substrings
    we use . as thousand separator and , as decimal one
    
    >>> list(FindNumbers('no numbers here'))
    []
    >>> list(FindNumbers('this is the n. 1 simple test'))
    [(15, 16, '1')]
    >>> list(FindNumbers('this is the n. +1 simple test'))
    [(16, 17, '1')]
    >>> list(FindNumbers('another -1 simple test'))
    [(8, 10, '-1')]
    >>> list(FindNumbers('more complex -4,01 test'))
    [(13, 18, '-4,01')]
    >>> list(FindNumbers('more complex +4,01 test 123,21'))
    [(14, 18, '4,01'), (24, 30, '123,21')]
    >>> list(FindNumbers('more complex 123.124,01 test 123.456.789,211.0'))
    [(13, 23, '123.124,01'), (29, 44, '123.456.789,211'), (45, 46, '0')]
    >>> list(FindNumbers('more and more complex 1+22+333+22.333+22,333+4.444+55.555,5 test'))
    [(22, 23, '1'), (24, 26, '22'), (27, 30, '333'), (31, 37, '22.333'), (38, 44, '22,333'), (45, 50, '4.444'), (51, 59, '55.555,5')]
    """
    
#    nreg = r"[-+]?[,]?[\d]+(?:.\d\d\d)*[\,]?\d*(?:[eE][-+]?\d+)?"
    nreg = r"-?[,]?[\d]+(\.\d\d\d)*[\,]?\d*"
    for m in re.finditer(nreg, text):
        yield (m.start(), m.end(), m[0])
    
 
if __name__ == "__main__":
    import doctest
    doctest.testmod()
