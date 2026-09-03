import os
import json
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_tavily import TavilySearch


class DuckDuckGoPlaceSearchTool:
    def __init__(self):
        self.search_tool = DuckDuckGoSearchRun()

    def ddg_search_attractions(self, place: str) -> str:
        """
        Searches for attractions in the specified place using DuckDuckGo Search.
        """
        return self.search_tool.invoke(f"top attractions and places to visit in and around {place}")

    def ddg_search_restaurants(self, place: str) -> str:
        """
        Searches for restaurants in the specified place using DuckDuckGo Search.
        """
        return self.search_tool.invoke(f"top 10 restaurants and food places to eat in {place}")

    def ddg_search_activity(self, place: str) -> str:
        """
        Searches for popular activities in the specified place using DuckDuckGo Search.
        """
        return self.search_tool.invoke(f"top activities and things to do in {place}")

    def ddg_search_transportation(self, place: str) -> str:
        """
        Searches for available modes of transportation in the specified place using DuckDuckGo Search.
        """
        return self.search_tool.invoke(f"public transit and transportation options in {place}")


class TavilyPlaceSearchTool:
    def __init__(self) -> None:
        pass

    def tavily_search_attractions(self, place: str) -> dict:
        """
        Searches for attractions in the specified place using TavilySearch.
        """
        tavily_tool = TavilySearch(topic='general', include_answer="advanced")
        result = tavily_tool.invoke({"query": f"top attractive places in and around {place}"})

        if isinstance(result, dict) and result.get("answer"):
            return result["answer"]
        return result

    def tavily_search_restaurants(self, place: str) -> dict:
        """
        Searches for available restaurants in the specified place using TavilySearch.
        """
        tavily_tool = TavilySearch(topic="general", include_answer="advanced")
        result = tavily_tool.invoke({"query": f"what are the top 10 restaurants and eateries in and around {place}."})
        if isinstance(result, dict) and result.get("answer"):
            return result["answer"]
        return result

    def tavily_search_activity(self, place: str) -> dict:
        """
        Searches for popular activities in the specified place using TavilySearch.
        """
        tavily_tool = TavilySearch(topic="general", include_answer="advanced")
        result = tavily_tool.invoke({"query": f"activities in and around {place}"})
        if isinstance(result, dict) and result.get("answer"):
            return result["answer"]
        return result

    def tavily_search_transportation(self, place: str) -> dict:
        """
        Searches for available modes of transportation in the specified place using TavilySearch.
        """
        tavily_tool = TavilySearch(topic="general", include_answer="advanced")
        result = tavily_tool.invoke({"query": f"What are the different modes of transportations available in {place}"})
        if isinstance(result, dict) and result.get("answer"):
            return result["answer"]
        return result