import abc
import functools
import os

import requests

import octoproxy


MATTERMOST_WEBHOOK = os.environ.get("MATTERMOST_WEBHOOK")
SHOW_AVATARS = bool(os.environ.get("SHOW_AVATARS", True))
OPENED_COLOR = os.environ.get("OCTOPROXY_OPENED_COLOR", "#F86864")
ASSIGNED_COLOR = os.environ.get("OCTOPROXY_ASSIGNED_COLOR", "#F8A864")
COMMENTED_COLOR = os.environ.get("OCTOPROXY_COMMENTED_COLOR", "#3D9296")
MERGED_COLOR = os.environ.get("OCTOPROXY_MERGED_COLOR", "#4EC356")


def add_payload_boilerplate(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        result = f(*args, **kwargs)
        return {"attachments": [result]}
    return wrapped


class Payload(object):
    """
    Abstract base class for Payloads.

    Borrowed from: https://github.com/softdevteam/mattermost-github-integration/blob/master/payload.py
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, data):
        self.data = data

    def _create_user_link(self, name, url, avatar):
        if SHOW_AVATARS:
            return "![](%s) [%s](%s)" % (avatar, name, url)
        return "[%s](%s)" % (name, url)

    @property
    def user_link(self):
        return self._create_user_link(self.sender_name, self.sender_url, self.sender_avatar)

    @property
    def repo_link(self):
        return "[{self.repo_name}]({self.repo_url})".format(self=self)

    @property
    def repo_name(self):
        return self.data["repository"]["full_name"]

    @property
    def repo_url(self):
        return self.data["repository"]["html_url"]

    @property
    def sender_name(self):
        return self.data["sender"]["login"]

    @property
    def sender_avatar(self):
        return self.data["sender"]["avatar_url"] + "&s=18"

    @property
    def sender_url(self):
        return self.data["sender"]["html_url"]

    @property
    def assignee_name(self):
        if self.data["issue"].get('assignee'):
            return self.data["issue"]["assignee"]["login"]
        else:
            return "(Nobody)"

    @property
    def assignee_avatar(self):
        if self.data["issue"].get('assignee'):
            return self.data["issue"]["assignee"]["avatar_url"] + "&s=18"
        else:
            return ""

    @property
    def assignee_url(self):
        if self.data["issue"].get('assignee'):
            return self.data["issue"]["assignee"]["html_url"]
        else:
            return ""

    @property
    def labels(self):
        return ", ".join(label.get("name") for label in self.data.get("labels", [{"name": "(None)"}]))

    @abc.abstractproperty
    def title(self):
        return NotImplemented

    @abc.abstractproperty
    def body(self):
        return NotImplemented

    @abc.abstractproperty
    def number(self):
        return NotImplemented

    @abc.abstractproperty
    def url(self):
        return NotImplemented

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
    """
    Models issue payloads.

    Borrowed from: https://github.com/softdevteam/mattermost-github-integration/blob/master/payload.py
    """
    @property
    def number(self):
        return self.data["issue"]["number"]

    @property
    def title(self):
        return self.data["issue"]["title"]

    @property
    def body(self):
        return self.data["comment"]["body"]

    @property
    def url(self):
        return self.data["comment"]["html_url"]

    @add_payload_boilerplate
    def created(self):
        preview = self.preview(self.body)
        fallback = ("{self.user_link} commented on an issue "
                    "[#{self.number} {self.title}]({self.url}) in {self.repo_link}:\n > "
                    "{preview}").format(self=self, preview=preview)
        return {
            "fallback": fallback,
            "color": COMMENTED_COLOR,
            "author_name": self.sender_name,
            "author_icon": self.sender_avatar,
            "author_link": self.sender_url,
            "title": "#{self.number} {self.title}".format(self=self),
            "title_link": self.url,
            "text": preview,
            "fields": [
                {"short": True,
                 "title": "Author",
                 "value": self.sender_name},
                {"short": True,
                 "title": "Assignee",
                 "value": self.assignee_name},
                {"short": True,
                 "title": "Labels",
                 "value": self.labels},
            ]
        }


class PullRequest(Payload):
    """ Models pull request payloads.

    Borrowed from: https://github.com/softdevteam/mattermost-github-integration/blob/master/payload.py
    """
    @property
    def number(self):
        return self.data["pull_request"]["number"]

    @property
    def title(self):
        return self.data["pull_request"]["title"]

    @property
    def body(self):
        return self.data["pull_request"]["body"]

    @property
    def url(self):
        return self.data["pull_request"]["html_url"]

    @property
    def action(self):
        merged = self.data["pull_request"]["merged"]
        return "merged" if merged else "closed"

    @add_payload_boilerplate
    def opened(self):
        preview = self.preview(self.body)
        fallback = ("{self.user_link} opened new pull request [#{self.number} {self.title}]({self.url}) "
                    "in {self.repo_link}:\n > {preview}").format(self=self, preview=preview)
        return {
            "fallback": fallback,
            "color": OPENED_COLOR,
            "author_name": self.sender_name,
            "author_icon": self.sender_avatar,
            "author_link": self.sender_url,
            "title": "#{self.number} {self.title}".format(self=self),
            "title_link": self.url,
            "text": preview,
            "fields": [
                {"short": True,
                 "title": "Author",
                 "value": self.sender_name},
                {"short": True,
                 "title": "Assignee",
                 "value": self.assignee_name},
                {"short": True,
                 "title": "Labels",
                 "value": self.labels}
            ]
        }

    @add_payload_boilerplate
    def assigned(self):
        assignee = self._create_user_link(self.assignee_name, self.assignee_url, self.assignee_avatar)
        fallback = ("{self.user_link} assigned {assignee} to pull request "
                    "[#{self.number} {self.title}]({self.url}).").format(self=self, assignee=assignee)
        return {
            "fallback": fallback,
            "color": ASSIGNED_COLOR,
            "author_name": self.sender_name,
            "author_icon": self.sender_avatar,
            "author_link": self.sender_url,
            "title": "#{self.number} {self.title}".format(self=self),
            "title_link": self.url,
            "fields": [
                {"short": True,
                 "title": "Author",
                 "value": self.sender_name},
                {"short": True,
                 "title": "Assignee",
                 "value": self.assignee_name},
                {"short": True,
                 "title": "Labels",
                 "value": self.labels},
            ]
        }

    @add_payload_boilerplate
    def closed(self):
        fallback = ("{self.user_link} {self.action} pull request "
                    "[#{self.number} {self.title}]({self.url})").format(self=self)
        return {
            "fallback": fallback,
            "color": MERGED_COLOR,
            "author_name": self.sender_name,
            "author_icon": self.sender_avatar,
            "author_link": self.sender_url,
            "title": "#{self.number} {self.title}".format(self=self),
            "title_link": self.url,
            "fields": [
                {"short": True,
                 "title": "Author",
                 "value": self.sender_name},
                {"short": True,
                 "title": "Assignee",
                 "value": self.assignee_name},
                {"short": True,
                 "title": "Labels",
                 "value": self.labels},
            ]
        }


@octoproxy.events.register_event("pull_request", repository="*")
def pull_request_receiver(event_type, event_data):
    payload_factory = PullRequest(event_data)
    payload = getattr(payload_factory, event_data["action"])()
    requests.post(MATTERMOST_WEBHOOK, json=payload)


@octoproxy.events.register_event("issue_comment", repository="*")
def issue_comment_receiver(event_type, event_data):
    payload_factory = IssueComment(event_data)
    payload = getattr(payload_factory, event_data["action"])()
    requests.post(MATTERMOST_WEBHOOK, json=payload)


if __name__ == "__main__":
    octoproxy.app.run("0.0.0.0", port=5050)
