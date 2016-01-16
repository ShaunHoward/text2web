__author__ = 'Shaun Howard'


def text2web(text):
    """
    Interprets the provided text as a web control command if possible.
    A message is returned to the user in text to describe the status
    of the operation.
    :param text: the text to control the default web browser
    :return: the text response of the web control service
    """
    # assert input is a string
    assert type(text) is str
    controls, status = parse(text)
    status = control_web(controls)
    return status
