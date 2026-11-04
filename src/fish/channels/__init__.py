"""The phone line. Terminal, and WeChat through Tencent's ClawBot (iLink) channel.
Only this package knows about I/O; the brain gets plain text."""

from fish.channels.base import Channel
from fish.channels.ilink import ILinkClient, ILinkError, SessionExpired
from fish.channels.one_line import SecondHer, hold_the_line
from fish.channels.terminal import TerminalChannel
from fish.channels.wechat import WeChatChannel, WeChatState, login

__all__ = ["Channel", "ILinkClient", "ILinkError", "SecondHer", "SessionExpired", "TerminalChannel",
           "WeChatChannel", "WeChatState", "hold_the_line", "login"]
