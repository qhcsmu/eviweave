"""Frozen query guard expressions from token-retrieval research."""
import re

MULTI = re.compile('\\b(?:all|both|each|every|list|compare|comparison|changes|changed|timeline|events|times|how many|over time|before and after|throughout)\\b', re.I)
RULE_QUERY = re.compile('\\b(?:rules?|instructions?|procedures?|polic(?:y|ies)|requirements?|steps?|format)\\b', re.I)
