from utils.place_info_search import DuckDuckGoPlaceSearchTool, TavilyPlaceSearchTool
from typing import List
from langchain.tools import tool


class PlaceSearchTool:
    def __init__(self):
        self.ddg_places_search = DuckDuckGoPlaceSearchTool()
        self.tavily_places_search = TavilyPlaceSearchTool()
        self.place_search_tool_list = self.__setup_tools()

    def __setup_tools(self) -> List:
        """Setup all tools for the place search tool"""

        @tool
        def search_attractions(place: str) -> str:
            """Search attractions of a place"""
            try:
                attraction_result = self.ddg_places_search.ddg_search_attractions(place)
                if attraction_result:
                    return f"Following are the attractions of {place}: {attraction_result}"
            except Exception as e:
                try:
                    tavily_result = self.tavily_places_search.tavily_search_attractions(place)
                    return f"Following are the attractions of {place}: {tavily_result}"
                except Exception as t_err:
                    return f"Could not retrieve attractions for {place}: {e} / {t_err}"

        @tool
        def search_restaurants(place: str) -> str:
            """Search restaurants of a place"""
            try:
                restaurant_result = self.ddg_places_search.ddg_search_restaurants(place)
                if restaurant_result:
                    return f"Following are the restaurants in {place}: {restaurant_result}"
            except Exception as e:
                try:
                    tavily_result = self.tavily_places_search.tavily_search_restaurants(place)
                    return f"Following are the restaurants in {place}: {tavily_result}"
                except Exception as t_err:
                    return f"Could not retrieve restaurants for {place}: {e} / {t_err}"

        @tool
        def search_activities(place: str) -> str:
            """Search activities of a place"""
            try:
                activity_result = self.ddg_places_search.ddg_search_activity(place)
                if activity_result:
                    return f"Following are the activities in and around {place}: {activity_result}"
            except Exception as e:
                try:
                    tavily_result = self.tavily_places_search.tavily_search_activity(place)
                    return f"Following are the activities in and around {place}: {tavily_result}"
                except Exception as t_err:
                    return f"Could not retrieve activities for {place}: {e} / {t_err}"

        @tool
        def search_transportations(place: str) -> str:
            """Search transportation of a place"""
            try:
                transport_result = self.ddg_places_search.ddg_search_transportation(place)
                if transport_result:
                    return f"Following are the transportation options in {place}: {transport_result}"
            except Exception as e:
                try:
                    tavily_result = self.tavily_places_search.tavily_search_transportation(place)
                    return f"Following are the transportation options in {place}: {tavily_result}"
                except Exception as t_err:
                    return f"Could not retrieve transportation for {place}: {e} / {t_err}"

        return [search_activities, search_attractions, search_restaurants, search_transportations]