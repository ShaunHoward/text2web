__author__ = 'Shaun Howard'
import json
import web

from helpers import log
from text_processor.text_processor import TextProcessor
from web_control_mapper.mapper import Mapper

urls = ("/.*", "WebJargon")
web_app = web.application(urls, globals())
err_msg = "Error: Command could not be processed.\n"

# use this template to send the text request
json_template = "{\"request\":\"open my friends list on facebook.\"}"


class WebJargon():
    mapper = None
    processor = None

    def __init__(self):
        self.mapper = Mapper()
        self.processor = TextProcessor()

    def GET(self):
        return 'Please provide Web Jargon with an English text web action request.'

    def POST(self):
        try:
            english_request = web.data()
            log(['received request: ', english_request])
            return extract_web_actions(english_request, self.processor, self.mapper)
        except ValueError:
            log(["could not process English request..."])
        return err_msg


def wrap_actions_in_json(web_actions):
    json_dict = dict()
    json_dict["actions"] = web_actions
    return json.dumps(json_dict)


def extract_web_actions(text, processor, mapper):
    """
    Interprets the provided text as a web control command if possible.
    A message may be returned to the user in json to describe the status
    of the operation.
    :param text: the text to control the default web browser
    :param processor: the processor instance to find the actions asked for
    :param mapper: the mapper instance for determining action list
    :return: the json text response of the web control service containing web actions to execute
    """
    # assert input is a string
    assert type(text) is str
    web_commands = processor.process_web_action_requests(text)
    web_actions = mapper.create_web_actions(web_commands)
    json_action_response = wrap_actions_in_json(web_actions)
    return json_action_response

if __name__ == '__main__':
    web_app.run()
