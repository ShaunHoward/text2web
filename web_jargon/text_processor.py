__author__ = 'shaun'

from itertools import chain

from os import path
import re
from nltk import sent_tokenize, word_tokenize
from nltk.corpus import wordnet as wn
from nltk.tag import StanfordPOSTagger
import helpers as h
from arg_parsers import WordsToNumbers


NUM_TO_INT = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
              "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
              "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20}

SUCCESS = "The operation was successful."
FAIL = "The operation was unsuccessful."

# context names
DEFAULT = "default"
FACEBOOK = "facebook"
SPOTIFY = "spotify"
GOOGLE = "google"
YOUTUBE = "youtube"

# custom tags
CMD_START = 'VB|NN'
CONTEXT = 'context'
DEFAULT_ACTION_CONTEXT = "default"
DIR = path.dirname(path.dirname(__file__))
DEFAULT_ACTIONS_PATH = DIR + '/templates/action_command_templates.txt'
STANFORD_JAR_PATH = DIR + '/postagger/stanford-postagger.jar'
BIDIR_STANFORD_TAGGER_PATH = DIR + '/postagger/models/english-bidirectional-distsim.tagger'
TWORD_STANFORD_TAGGER_PATH = DIR + '/postagger/models/english-left3words-distsim.tagger'


def similar_words(word, meaning):
    """
    Find words similar to the given word with the
    given meaning, tagged with POS by nltk.
    """
    word_w_meaning = word + meaning
    word_synset = wn.synset(word_w_meaning)
    print "definition of %s" % word
    print word_synset.definition()
    # gather synonyms from lemmas, hyponyms (sub-types) and hypernyms (super-types)
    synonyms = word_synset.lemma_names() \
        + list(chain(*[l.lemma_names for l in word_synset.hyponyms()])) \
        + list(chain(*[l.lemma_names for l in word_synset.hypernyms()]))
    print "synonyms: "
    print ', '.join(synonyms)
    return synonyms


def fuzzy_action_interpreter(command_tags, command_words, curr_action_request):
    # do fuzzy action interpretation
    tag_list = []
    for j in range(len(command_tags)):
        tag = command_tags[j]
        # look for a command start
        if ('VB' in tag and CMD_START not in tag_list) or\
                ('NN' in tag and CMD_START not in tag_list):
            tag_list.append(CMD_START)
            command_start = j
            # add command start to dictionary
            curr_action_request[h.CMD] = command_words[command_start]
        # look for command modifiers like up, down, etc.
        elif ('RB' in tag or 'RP' in tag or
                ('VB' in tag and CMD_START in tag_list) or
                ('NN' in tag and CMD_START in tag_list)) and\
                command_start == 0:
            if j > command_start:
                tag_list.append('RB|RP|VB')
                curr_action_request[h.CMD] += ''.join([' ', command_words[j]])
        # look for numeral values to feed as arguments to command
        elif 'CD' in tag or 'JJ' in tag:
            tag_list.append('CD|JJ')
            # try to parse a number out of the numeral
            if 'JJ' in tag and command_words[j] in NUM_TO_INT.keys():
                num_arg = NUM_TO_INT[command_words[j]]
                curr_action_request[h.CMD_ARGS_DICT].append(num_arg)
            else:
                curr_action_request[h.CMD_ARGS_DICT].append(command_words[j])
    return curr_action_request


def load_training_data(training_data_dir):
    with open(training_data_dir, 'r') as training_file:
        training_data = training_file.read()
    training_data_list = training_data.split('\n')
    return training_data_list


def extract_match(str_to_search, matcher):
    match = matcher.match(str_to_search)
    parsed_arg = ''
    if match is not None and len(match.group()) > 0:
        parsed_arg = match.group()
    return parsed_arg


def break_into_multiple_actions(words, tags):
    """
    Uses the given tags to determine where to split the given words into
    separate action requests. This facilitates the ability to interpret multiple
    commands given at once.
    :param words: the words of the sentences spoken
    :param tags: the tags of the words in the sentences spoken
    :return: the commands and tags of the split up action requests
    """
    commands = []
    command_tags = []
    # break into multiple action requests on conjunctions
    if 'CC' in tags:
        conjunctions = []
        for i in range(len(tags)):
            if 'CC' in tags[i]:
                conjunctions.append(i)

        # split up commands by splitting sentence on conjunctions
        split_indices = [x for x in conjunctions] + [len(words)]
        curr_words_ = words
        curr_tags_ = tags
        offset = 0
        conj_removed = True
        for i in split_indices:
            i_ = i - offset
            curr_words = curr_words_[:i_]
            if i_ < len(curr_words_):
                conjunction = curr_words_[i_]
                conj_tag = curr_tags_[i_]
                conj_removed = False
            # remove the first half of the sentence from the list
            [curr_words_.remove(x) for x in curr_words]
            curr_tags = curr_tags_[:i_]
            [curr_tags_.remove(x) for x in curr_tags]
            # remove the conjunction as well
            if not conj_removed:
                curr_words_.remove(conjunction)
                # remove the conjunction tag as well
                curr_tags_.remove(conj_tag)
                conj_removed = True
                # track an offset for future operations
                offset += len(curr_words) + 1
            else:
                # track an offset for future operations
                offset += len(curr_words)
            # add these to the list
            commands.append(curr_words)
            command_tags.append(curr_tags)
    else:
        commands.append(words)
        command_tags.append(tags)
    return commands, command_tags


class TextProcessor():

    action_text_mappings = dict()
    basic_name_pattern = "[a-zA-Z\s]+$"
    valid_web_jargon_pattern = "^[\s\w\d\>\<\;\,\{\}\[\]\-\_\+\=\!\@\#\$\%\^\&\*\|\'\.\:\(\)\\\/\"\?]+$"
    url_pattern = ".*(\.|dot) ?[a-z]{2,3}"
    basic_name_matcher = None
    web_jargon_matcher = None
    words_to_numbers = None
    url_matcher = None
    PATTERN_DICT = dict()

    def __init__(self):

        self.words_to_numbers = WordsToNumbers()
        self.create_argument_pattern_dict()
        self.basic_name_matcher = re.compile(self.basic_name_pattern)
        self.web_jargon_matcher = re.compile(self.valid_web_jargon_pattern)
        self.url_matcher = re.compile(self.url_pattern)
        self.action_text_mappings = h.load_web_action_template(DEFAULT_ACTIONS_PATH, False)
        self.split_action_keys = [x.split("_") for x in self.action_text_mappings.keys()]
        self.st = StanfordPOSTagger(TWORD_STANFORD_TAGGER_PATH, STANFORD_JAR_PATH)

    def tag_words(self, words_of_text):
        """
        Tags the provided words of the text with parts of speech.
        :param words_of_text: the text to tag the words of
        :return: the tags of the words in a list
        """
        tags = []
        tag_tuple_list = self.st.tag(words_of_text)
        for tag_tuple in tag_tuple_list:
            tag = tag_tuple[1]
            tags.append(tag)
        return tags

    def create_argument_pattern_dict(self):
        self.PATTERN_DICT = {'ELEMENT_NAME': self.match_web_jargon,
                             'NUM_PAGES': self.words_to_numbers.parse, 'PERCENT': self.words_to_numbers.parse,
                             'TAB_INDEX': self.tab_index, 'TAB_NAME': self.basic_names,
                             'URL': self.url, 'FORM_NAME': self.basic_names, 'EXCERPT': self.match_web_jargon,
                             'BUTTON_NAME': self.basic_names,
                             'PAGE_NUM': self.words_to_numbers.parse, 'LINK_NAME': self.match_web_jargon}

    def basic_names(self, text):
        return extract_match(text, self.basic_name_matcher)

    def match_web_jargon(self, text):
        return extract_match(text, self.web_jargon_matcher)

    def valid_web_jargon(self, text):
        """
        Text is valid web jargon if it is good English of type str or unicode that is non-empty.
        :param text: the web jargon request
        :return: whether the input text is valid web jargon aka good English, no weird characters
        """
        return (type(text) is str or type(text) is unicode)\
            and len(text) > 0 and len(self.web_jargon_matcher.match(text).group()) > 0

    def process_web_action_requests(self, text):
        """
        Parses the provided text into web text actions that will be converted into
        web actions by the web text to action mapper. The order will be maintained.
        :param text: the input command text
        :return: the controls list, which will be empty if in error
        """
        web_action_tokens = []
        if self.valid_web_jargon(text):
            # tokenize text into sentences
            sentences = sent_tokenize(text)

            # determine valid sentences
            valid_sentences = [sent for sent in sentences if self.valid_web_jargon(sent)]

            # extract words corresponding to valid sentences
            words_of_sentences = [word_tokenize(sent) for sent in valid_sentences]

            # get the tags of words
            tags_of_sentences = [self.tag_words(words) for words in words_of_sentences]

            # extract action requests from the current command and add to web action token list
            web_action_tokens = []

            for i in range(len(words_of_sentences)):
                words = words_of_sentences[i]
                tags = tags_of_sentences[i]
                curr_requests = self.extract_action_requests(text, words, tags)
                for request in curr_requests:
                    web_action_tokens.append(request)
        else:
            if type(text) is str or unicode:
                h.log(["invalid request received: ", text])
            else:
                h.log(["invalid request type, received: ", str(type(text)), " but expected str or unicode..."])

        return web_action_tokens

    def extract_action_requests(self, text, words, tags=None):
        """
        Figure out the web actions that exist in the provided sentence using
        the given words and tags as well as action command templates.
        :param text: the text said by the user
        :param words: the words of the sentence
        :param tags: the tags of the words in the sentence
        :return: the web actions tokens and arguments
        """
        # search for conjunctions to split up commands
        commands, command_tags = break_into_multiple_actions(words, tags)

        # interpret actions
        action_requests = []

        for i in range(len(commands)):
            command_words = commands[i]
            curr_command_tags = command_tags[i]
            # only need command part of text
            command_text = ' '.join(command_words)
            # first try to use templates to determine desired actions
            curr_action_request = self.template_action_interpreter(command_text, command_words)
                                                                    #command_tags, curr_action_request)

            # next try to use the fuzzy nlp interpreter to determine desired actions
            if len(curr_action_request) == 0:
                curr_action_request = fuzzy_action_interpreter(curr_command_tags, command_words, curr_action_request)

            # add actions if intent determine, otherwise print error message
            if len(curr_action_request) > 0:
                action_requests.append(curr_action_request)
            else:
                print "error in interpreting desired actions..."

        return action_requests

    def template_action_interpreter(self, command_text, command_words):
        """
        This method will not always work. multiple instances of the same string may be detected
        in matching and may throw off the interpreter.
        :param command_text: the command text for the current action request
        :param command_words: the command words for the current action request
        :return:
        """

        # store lowercase of all strings and filter out quotes
        command_words = [x.lower() for x in command_words if x != '``' and x != '\'\'']

        # store lowercase, parens removed, stripped version of command text input
        command_text = command_text.lower().strip().lstrip("\"").rstrip("\"").strip()

        # found_action = False
        # store matches list
        matches = []
        has_exact_match = False
        # try to find match for command in templates
        for action_key in self.action_text_mappings.keys():
            if not has_exact_match:
                for u_map in self.action_text_mappings[action_key]:
                    indices = []
                    curr_command_text = command_text
                    curr_command_words = [x for x in command_words]
                    # track the number of words not found in the command words list
                    num_left_out = 0
                    for part in u_map[h.PARTS]:
                        # check if part of the utterance is in the command
                        if part in curr_command_text:
                            part_start = command_text.index(part)
                            part_end = part_start + len(part)
                            indices.append((part_start, part_end))
                            # replace that part of string with underscore to signify removal
                            curr_command_text = curr_command_text.replace(part, '')
                            # remove this part from the word list (if not in list, problem but neglect)
                            part_split = part.split(" ")
                            for p in part_split:
                                if p in curr_command_words:
                                    curr_command_words.remove(p)
                                else:
                                    num_left_out += 1

                    # store match if parts are in command
                    if len(indices) == len(u_map[h.PARTS]):

                        # store indices where args will be extracted from in string
                        arg_sections = h.extract_arg_sections(command_text, indices)

                        # do smart argument parsing use regex, parse trees, etc.
                        args = u_map[h.CMD_ARGS_DICT].copy()
                        req_args = len(args)
                        num_args = 0
                        for arg_type in u_map[h.CMD_ARGS_DICT]:
                            # extract argument using argument type
                            parsed_arg = self.match_arg(arg_type, curr_command_words, arg_sections)
                            if (type(parsed_arg) == int and parsed_arg > 0)\
                                    or (type(parsed_arg) == list
                                        or type(parsed_arg) == str and len(parsed_arg) > 0):
                                args[arg_type] = parsed_arg
                                num_args += 1
                        # this is an exact match
                        if num_args == len(args) and len(curr_command_words) == 0 and num_left_out == 0:
                            matches = [(action_key, " ".join(u_map[h.PARTS]), args, min(indices[:][0]), num_args, req_args)]
                            has_exact_match = True
                            break
                        else:
                            # otherwise, keep appending matches
                            matches.append((action_key, " ".join(u_map[h.PARTS]), args, min(indices[:][0]), num_args, req_args))

        curr_action_request = dict()
        # select the earliest and/or longest command match for the current action request
        if len(matches) > 0:
            longest_phrase = 0
            most_args = 0
            earliest_pos = 0
            earliest_index = 0
            ctr = 0
            for match in matches:
                # get length of parts string that matched command
                mlen = len(match[1])
                # get start pos of command match
                start_pos = match[3]

                # get the number of args matched from phrase
                num_args = match[4]

                req_args = match[5]

                # look for longer phrase
                if mlen > longest_phrase and (req_args == num_args or most_args < num_args):
                    longest_phrase = mlen
                    # take longer phrase (still same starting location)
                    if start_pos == earliest_pos:
                        earliest_pos = start_pos
                        earliest_index = ctr

                # look for same length phrase with earlier command match
                if start_pos < earliest_pos or (start_pos == earliest_pos and mlen == longest_phrase):
                    most_args = num_args
                    earliest_pos = start_pos
                    earliest_index = ctr
                ctr += 1

                # set command and args from action text mappings
                curr_action_request[h.CMD] = matches[earliest_index][0]
                curr_action_request[h.CMD_ARGS_DICT] = matches[earliest_index][2]

        return curr_action_request

    def tab_index(self, words):
        """
        Convert the words to a number index
        :param words:
        :return:
        """
        result = self.words_to_numbers.parse(words)
        if result < 0:
            result = self.get_index(words.split(" "))
        return result

    @staticmethod
    def get_index(words):
        """
        Returns a the number of an English number index (indicating element position) found in the provided list of words.
        :param words: the list of words to find the English number index in
        :return: the number version of the found index
        """
        result = -1
        for word in words:
            if word in NUM_TO_INT.keys():
                result = NUM_TO_INT[word]
                break
        return result

    def url(self, words):
        # try to fix words and parse out a URL
        words.replace('dot ', '.')
        words.replace('dot', '.')
        words.replace('w w w ', 'www')
        words.replace('w w w', 'www')
        return extract_match(words, self.url_matcher)

    def match_arg(self, arg_type, command_words, arg_sections):
        """
        Tries to find the given arg type in the list of argument sections,
        using the provided command words as backup evidence in decision making.
        :param arg_type: the type of argument to search for as addressed by the global pattern dictionary
        in this class
        :param command_words: the words of the command to match to
        :param arg_sections: the already known argument sections in the command
        :return: the parsed argument from the given command and data
        """
        arg_sections = [x.strip() for x in arg_sections]
        parsed_arg = ''
        # may accept multiple argument types, so treat them independently
        if "|" in arg_type:
            arg_types = arg_type.split("|")
        else:
            # otherwise, just have one argument type to look for
            arg_types = [arg_type]

        # run search for pattern matches to argument types in the command text
        for arg_type in arg_types:
            if len(command_words) > 0 and len(arg_sections) > 0 and arg_type in self.PATTERN_DICT.keys():
                # extract the proper pattern
                pattern = self.PATTERN_DICT[arg_type]
                # The pattern may be a function call, strings mean regex patterns are given
                if type(pattern) is not str:
                    # match using a matching function that is callable
                    valid_match = False
                    for arg_section in arg_sections:
                        match = pattern(arg_section)
                        valid_match = (type(match) == int and match > 0) or (type(match) != int and match is not None)
                        if valid_match:
                            parsed_arg = match
                            break
                    if valid_match:
                        break
                else:
                    # compile a regex pattern on the fly (not really used in practice but always an option)
                    pat = re.compile(pattern)

                    # try to match to words first using regex
                    for word in command_words:
                        match = pat.match(word)
                        if match is not None and len(match.group()) > 0:
                            parsed_arg = match.group()
                            break

                    # otherwise, try to match to argument phrase sections
                    for arg_section in arg_sections:
                        match = pat.match(arg_section)
                        if match is not None and len(match.group()) > 0:
                            parsed_arg = match.group()
                            break
        return parsed_arg