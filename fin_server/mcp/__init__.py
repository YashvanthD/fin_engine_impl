"""MCP (Model Context Protocol) Server Package.

This package provides an MCP server for AI assistants to interact with
the Fin Engine application data through standardized tools and resources.
"""
from .server import MCPServer
from .tools import MCPTools

__all__ = ['MCPServer', 'MCPTools']

