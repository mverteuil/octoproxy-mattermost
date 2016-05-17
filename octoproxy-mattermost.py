import os

import octoproxy
import requests


MATTERMOST_WEBHOOK = os.environ.get('MATTERMOST_WEBHOOK')
SHOW_AVATARS = bool(os.environ.get('SHOW_AVATARS', True))


class Payload(object):
    """ Base class for payloads.

    Borrowed from: https://github.com/softdevteam/mattermost-github-integration/blob/master/payload.py
    """
    def __init__(self, data):
        self.data = data

    def user_link(self):
        name   = self.data['sender']['login']
        url    = self.data['sender']['html_url']
        avatar = self.data['sender']['avatar_url'] + "&s=18"
        return self.create_user_link(name, url, avatar)

    def create_user_link(self, name, url, avatar):
        if SHOW_AVATARS:
            return "![](%s) [%s](%s)" % (avatar, name, url)
        return "[%s](%s)" % (name, url)

    def repo_link(self):
        name = self.data['repository']['full_name']
        url  = self.data['repository']['html_url']
        return "[%s](%s)" % (name, url)

    def preview(self, text):
        if not text:
            return text
        l = text.split("\n")
        result = l[0]
        if result[-1] in "[\n, \r]":
            result = result[:-1]
        if result != text:
            result += " [...]"
        return result


class IssueComment(Payload):
    """ Models issue payloads.

    Borrowed from: https://github.com/softdevteam/mattermost-github-integration/blob/master/payload.py
    """
    def __init__(self, data):
        Payload.__init__(self, data)
        self.number = self.data['issue']['number']
        self.title  = self.data['issue']['title']
        self.body   = self.data['comment']['body']
        self.url    = self.data['comment']['html_url']

    def created(self):
        body = self.preview(self.body)
        msg = """%s commented on an issue [#%s %s](%s) in %s:\n > %s""" % (
            self.user_link(), self.number, self.title,
            self.url, self.repo_link(), body)
        return msg


class PullRequest(Payload):
    """ Models pull request payloads.

    Borrowed from: https://github.com/softdevteam/mattermost-github-integration/blob/master/payload.py
    """
    def __init__(self, data):
        Payload.__init__(self, data)
        self.number = self.data['pull_request']['number']
        self.title  = self.data['pull_request']['title']
        self.body   = self.data['pull_request']['body']
        self.url    = self.data['pull_request']['html_url']

    def opened(self):
        body = self.preview(self.body)
        msg = """%s opened new pull request [#%s %s](%s) in %s:\n > %s""" % (
            self.user_link(), self.number, self.title,
            self.url, self.repo_link(), body)
        return msg

    def assigned(self):
        to_name   = self.data['assignee']['login']
        to_url    = self.data['assignee']['html_url']
        to_avatar = self.data['assignee']['avatar_url'] + "&s=18"
        to = self.create_user_link(to_name, to_url, to_avatar)
        msg = """%s assigned %s to pull request [#%s %s](%s).""" % (self.user_link(),
            to, self.number, self.title, self.url)
        return msg

    def closed(self):
        merged = self.data['pull_request']['merged']
        action = "merged" if merged else "closed"
        msg = """%s %s pull request [#%s %s](%s).""" % (self.user_link(),
            action, self.number, self.title, self.url)
        return msg


@octoproxy.events.register_event('pull_request', repository='*')
def pull_request_receiver(event_type, event_data):
    payload_factory = PullRequest(event_data)
    message = getattr(payload_factory, event_data['action'])()
    requests.post(MATTERMOST_WEBHOOK, data={'payload': message})


@octoproxy.events.register_event('issue_comment', repository='*')
def issue_comment_receiver(event_type, event_data):
    payload_factory = IssueComment(event_data)
    message = getattr(payload_factory, event_data['action'])()
    requests.post(MATTERMOST_WEBHOOK, data={'payload': message})



if __name__ == '__main__':
    octoproxy.app.run('0.0.0.0', port=5050)
