# bot/utilities/pyrofilters/__init__.py file :

from .admins import AdminsFilter
from .conversation import ConversationFilter, ConvoMessage
from .subscription import SubscriptionFilter, SubscriptionMessage


class PyroFilters:
    """A class to hold all the custom filters."""

    admin = AdminsFilter.admin
    convo = ConversationFilter.conversation
    sub = SubscriptionFilter.subscription
