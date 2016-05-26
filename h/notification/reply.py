# -*- coding: utf-8 -*-

from collections import namedtuple
import logging

from pyramid.events import subscriber

from h import auth
from h import accounts
from h.api import storage
from h.notification.models import Subscriptions
from h.accounts.events import RegistrationEvent

log = logging.getLogger(__name__)


class Notification(namedtuple('Notification', [
    'reply',
    'reply_user',
    'parent',
    'parent_user',
    'document',
])):
    """
    A data structure representing a notification of a reply to an annotation.

    :param reply: the reply annotation
    :type reply: h.models.Annotation (or h.api.models.elastic.Annotation)
    :param reply_user: the user who made the reply annotation
    :type reply_user: h.models.User
    :param parent: the annotation being replied to
    :type parent: h.models.Annotation (or h.api.models.elastic.Annotation)
    :param parent_user: the user being replied to
    :type parent_user: h.models.User
    :param document: the document for the page on which the reply happened
    :type document: h.models.Document (or h.api.models.elastic.Document)
    """


def get_notification(request, annotation, action):
    """
    Check if the passed annotation and action pair should send a notification.

    Checks to see if the annotation event represented by the passed annotation
    and action should trigger a notification. If it should, this function
    returns the relevant :py:class:`~h.notification.reply.Notification` object.
    Otherwise, it returns None.

    :param request: the current request object
    :type request: pyramid.request.Request
    :param annotation: the reply annotation
    :type annotation: h.api.models.elastic.Annotation or h.models.Annotation
    :param action: the event action
    :type action: str

    :returns: a :py:class:`~h.notification.reply.Notification`, or None
    """
    # Only send notifications when new annotations are created
    if action != 'create':
        return

    # If the annotation doesn't have a parent, or we can't find its parent,
    # then we can't send a notification email.
    parent_id = annotation.parent_id
    if parent_id is None:
        return

    # Now we know we're dealing with a reply
    reply = annotation

    parent = storage.fetch_annotation(request.db, parent_id)
    if parent is None:
        return

    # If the parent user doesn't exist (anymore), we can't send an email.
    parent_user = accounts.get_user(parent.userid, request)
    if parent_user is None:
        return

    # If the reply user doesn't exist (anymore), we can't send an email, but
    # this would be super weird, so log a warning.
    reply_user = accounts.get_user(reply.userid, request)
    if reply_user is None:
        log.warn('user who just replied no longer exists: %s', reply.userid)
        return

    # Do not notify users about their own replies
    if parent_user == reply_user:
        return

    # Don't send reply notifications to the author of the parent annotation if
    # the author doesn't have permission to read the reply.
    if not auth.has_permission(request, reply, parent.userid, 'read'):
        return

    # FIXME: we should be retrieving the document from the root annotation, not
    # the reply, and dealing with the possibility that we have no document
    # metadata.
    if reply.document is None:
        return

    # Bail if there is no active 'reply' subscription for the user being
    # replied to.
    sub = request.db.query(Subscriptions).filter_by(active=True,
                                                    type='reply',
                                                    uri=parent.userid).first()
    if sub is None:
        return

    return Notification(reply, reply_user, parent, parent_user, reply.document)


# Create a reply template for a uri
def create_subscription(request, uri, active):
    subs = Subscriptions(
        uri=uri,
        type='reply',
        active=active
    )

    request.db.add(subs)
    request.db.flush()


@subscriber(RegistrationEvent)
def registration_subscriptions(event):
    request = event.request
    user_uri = u'acct:{}@{}'.format(event.user.username, request.domain)
    create_subscription(event.request, user_uri, True)


def includeme(config):
    config.scan(__name__)
