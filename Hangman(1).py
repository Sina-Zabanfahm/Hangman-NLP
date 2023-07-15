#!/usr/bin/env python
# coding: utf-8

# In[19]:


import json
import random
import string
import time
import re
from collections import defaultdict
from functools import reduce


# In[219]:


class HangmanAPI(object):
    def __init__(home_game =True):
        self.hangman_url = self.determine_hangman_url()
        self.access_token = access_token
        self.session = session or requests.Session()
        self.timeout = timeout
        self.guessed_letters = []
        self.home_game=False
        """
        The inital approach had a lot of difficulty dealing with words starting with 'sh',
        it forces the guess state to guess 's' if none of the first three letters are 
        discovered yet.
        """
        self.vowels = ['e','a','i','o','u','s','y'] 
        
        
        full_dictionary_location = "words_250000_train.txt"
        
        self.current_dictionary = []
        self.full_dictionary = self.build_dictionary(full_dictionary_location)



        self.tries=0
        self.new_dictionary_in_use = False
        self.full_letter_set = set()
        
        
        self.full_letter_set = reduce(lambda x, y: set(x) | set(y), self.full_dictionary)
        
        
        """computes a hashcode for a pair of word and letters:
           For example:
           (apple,p) will be coded by 2^1 + 2^2 (01100)
           The result is then 
            It is designed for computational convenience later on in the guess function.
        """
        self.pattern = defaultdict(int)
        for word in self.full_dictionary:
            letter_set = set(word)
            for c in letter_set:
                indices = [index for index in range(len(word)) if word[index]==c]
                hash_code = 0
                for i in indices:
                    hash_code+= 2**i
                self.pattern[(word,c)] = hash_code

        self.current_dictionary = []
        
        """ngrams holds probability distribution of each pattern.
            The keys of the dictionary consists of a letter and a pattern
            For example self.ngrams[('a','.n.n.')] counts the pattern 
            'anana' appearing in words in the dictionary.
            
            Keys of ngrams are (letter, pattern) and values are ints.
        """
        self.ngrams = [defaultdict(int) for _ in range(6)]
        self.weights = {1: 0.05, 2: 0.1, 3:0.15, 4:0.2, 5: 0.4}
        self.build_grams(self.full_dictionary)
        self.ngrams_copy = self.ngrams.copy()
    def build_grams(self, current_dictionary):
        """
        It receives a dictionary current_dictionary, then loops through
        the words of the dictionary.
        
        self.ngrams[j][(letterr), masked_word] counts patters of
        masked word that can be completed with letter.
        """
        for word in current_dictionary:
            for i in range(len(word)):
                for j in range(1,6):
                    if i+j >len(word):
                        continue
                    current_word = word[i:i+j]
                    letter_set = set(current_word)
                    for letter in letter_set:
                        masked_word = current_word.replace(letter,'.')
                        #print(masked_word," ", word," ", len(masked_word)," ", j)
                        if j <= 2:
                            self.ngrams[j][(letter,masked_word,len(word))]+=1
                        else:
                            self.ngrams[j][(letter, masked_word)]+=1
    def get_probabilities(self, clean_word):
        """
        get_probabilities computes the frequency of patterns in clean_word which appears in words in 
        our current dictionary.
        
        Each pattern has at most 5 consecuitive letters, and its assumed that missing letters in the pattern
        is going to be filled by a single letter.
        
        For the patterns of length 1 and 2, it also remember the length of the word that this patterns coming from.
        (I did not use this property. The first iterations of guess function tries letters with high frequency
        int the training dictionary)
        """
        
        probs_by_letter = defaultdict(int)
        probs_by_size = defaultdict(int)
        total_by_size = defaultdict(int)
        letters_left = self.full_letter_set - set(self.guessed_letters)


        for letter in letters_left:
            for i in range(len(clean_word)):
                for j in range(1,6):
                    if i+j > len(clean_word):
                        continue
                    masked_word = clean_word[i:i+j]
                    if j<=2:
                        if i+j+2<len(clean_word) and (clean_word[i+j+1]!='.' or clean_word[i+j+2]!='.'):
                            continue
                        probs_by_size[(letter, j)] += self.ngrams[j][(letter,masked_word,len(clean_word))]
                        total_by_size[j]+= self.ngrams[j][(letter,masked_word,len(clean_word))]
                    else:
                        probs_by_size[(letter, j)] +=self.ngrams[j][(letter, masked_word)]
                        total_by_size[j]+=self.ngrams[j][(letter, masked_word)]

        for letter in letters_left:
            for j in range(1,6):
                if(total_by_size[j]==0):
                      continue
                probs_by_letter[letter]+=probs_by_size[(letter,j)]/total_by_size[j]*self.weights[j]
        #print(probs_by_letter)
        return probs_by_letter
    def update_dictionary(self,clean_word,guessed_letters_set):
        """
        This updates the dictionary. The overall algorithm have difficulty guessing the letters at the beginning of
        each word, most failed cases happens in the cases that the first word is undiscovered by the 3rd try.
        
        Its an attempt to remedy this situation, it filles up the dictionary with words with acceptable matching in missing
        word in the first few letters.
        
        """ 
        new_dictionary = []
        for dict_word in self.full_dictionary:
            if len(dict_word) < len(clean_word):
                if(len(dict_word)<4):
                    continue
                else:
                    dict_word = dict_word[:4]
            penalty = 0
            for i in range(min(len(clean_word),len(dict_word))):
                penalty += 0.25*(dict_word[i]!=clean_word[i] and clean_word[i]!='.') + 0.75*(clean_word[i]=='.' and (dict_word[i] in guessed_letters_set))
            dict_word=dict_word[0:min(len(dict_word),len(clean_word)+2)]
            new_dictionary.append([penalty, dict_word])

        new_dictionary = sorted(new_dictionary)
        current_dictionary = [new_dictionary[index][1] for index in range(len(new_dictionary)//2)]
        #print(len(current_dictionary))
        self.build_grams(current_dictionary)

    def guess(self, word): # word input example: "_ p p _ e "
        ###############################################
        # Replace with your own "guess" function here #
        ###############################################
        # clean the word so that we strip away the space characters
        # replace "_" with "." as "." indicates any character in regular expressions
        """
        The guess function works as follow:
        It starts with guessing vowels (and s), the ngram probabilites don't work very well when
        the letters are very separated. This guarantees a letter occurence in every four consecutive letters.
        
        Then it uses the training dictionary, it assumes that the word is in the dictionary and it try to locate
        it in the dictionary. It will do this until it exhust the dictionary or reaches a stage that 4 remaining
        guesses are left.
        
        Initially I tried to force each move to reduce the number of matching words in the dictionary at each
        iteration. But its better to guess a letter that is most likely is going to be part of the current word,
        this makes patterns probabilities a bit more accurate.
        
        Finally, when it reaches to two guesses it will update the dictionary.
        When it reaches to one guess left, it will update the dictionary at each iteration. This makes the whole
        algorithm extremely slow. However, it adds a few percent more accuracy.
        
        """
        
        clean_word = word[::2].replace("_",".")
        #print(clean_word)
        guessed_letters_set =set(self.guessed_letters)

        # find length of passed word
        len_word = len(clean_word)
        
        
        if (len(re.findall(r'[^aeiou][.]{3}',clean_word)) 
            or (len(re.findall(r'[.]{3}[^aeiou]',clean_word))) or clean_word =='...'):
            for v in self.vowels:
                if v not in guessed_letters_set:
                    return v
        
        # grab current dictionary of possible words from self object, initialize new possible words dictionary to empty
        if (len(self.current_dictionary) < 40 or self.tries<4):
            if( self.tries==2 and self.new_dictionary_in_use == False):
                self.new_dictionary_in_use =True
                self.update_dictionary(clean_word,guessed_letters_set)
            if (self.tries == 1):
                self.update_dictionary(clean_word,guessed_letters_set)

            probs_by_letter = self.get_probabilities( clean_word)
            guess_letter =  max(probs_by_letter, key=probs_by_letter.get)
            return guess_letter



        # grab current dictionary of possible words from self object, initialize new possible words dictionary to empty
        current_dictionary = self.current_dictionary
        new_dictionary = []

        # iterate through all of the words in the old plausible dictionary
        for dict_word in current_dictionary:
            # continue if the word is not of the appropriate length
            if len(dict_word) != len_word:
                continue

            # if dictionary word is a possible match then add it to the current dictionary
            if re.match(clean_word,dict_word):
                new_dictionary.append(dict_word)
            
        missed_indices = [index for index in range(len(clean_word)) if  clean_word[index]=='.']
        """
        dict_count should have integer values. Initially I was trying something else which didnt work very
        well.
        """
        dict_count= defaultdict(list)
        for dict_word in current_dictionary:
            if len(dict_word)!=len_word:
                continue
            if re.match(clean_word,dict_word):
                dict_word_set = set()
                for index in missed_indices:
                    dict_word_set.add(dict_word[index])

                if len(dict_word_set.intersection(set(guessed_letters_set)))!=0:
                    continue
                new_dictionary.append(dict_word)
                for c in dict_word_set:
                    dict_count[c].append(dict_word)
        self.current_dictionary = new_dictionary

        guess_letter = '!'
        max_info = 0
        for c in dict_count.keys():
            if len(dict_count[c])>max_info:
                max_info = len(dict_count[c])
                guess_letter = c

        # return most frequently occurring letter in all possible words that hasn't been guessed yet

        # if no word matches in training dictionary, default back to ordering of full dictionary
        if guess_letter == '!':
            self.current_dictionary = []
            return self.guess(word)
        else:
            return guess_letter

    def build_dictionary(self, dictionary_file_location):
        text_file = open(dictionary_file_location,"r")
        full_dictionary = text_file.read().splitlines()
        text_file.close()
        return full_dictionary
    
    def start_game(self, practice=True, verbose=True, home_game=True):
        # reset guessed letters to empty set and current plausible dictionary to the full dictionary
        self.weights = {1: 0.05, 2: 1, 3:0.15, 4:0.2, 5: 0.40}

        self.current_dictionary = self.full_dictionary
        self.guessed_letters=[]
        self.new_dictionary_in_use=False
        self.ngrams = self.ngrams_copy
        if(self.home_game == True):
            hidden_word = self.test_dictionary[random.randint(0, len(self.test_dictionary)-1)]
            print(hidden_word)

            word = ""
            for i in range(len(hidden_word)):
                word+="_" + " "

            tries_remains = 6

            self.current_dictionary = self.full_dictionary
            while tries_remains > 0:
                self.tries = tries_remains
                #print(word)
                guess_letter = self.guess(word)
                self.guessed_letters.append(guess_letter)
                #print(guess_letter)
                if guess_letter not in hidden_word:
                    #print(f'{guess_letter} is not in this in this word\n')
                    tries_remains-=1;
                elif guess_letter in set(hidden_word):
                    word = list(word)
                    for i in range(len(hidden_word)):
                        if hidden_word[i] == guess_letter:
                            word[2*i] = guess_letter
                    word = ''.join(word)

                if word.count('_') == 0:
                   # print(f'{hidden_word}, {word} Success')
                    return 1
                self.guessed_letters.append(guess_letter)
            #print(f'Failure {hidden_word}, {word}')
            return 0




    
 

