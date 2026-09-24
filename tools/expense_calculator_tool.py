from utils.expense_calculator import Calculator
from langchain.tools import tool
from typing import List, Union

class CalculatorTool():
    def __init__(self) -> None:
        self.calculator = Calculator()
        self.calculator_tool_list = self._setup_tools()

    def _setup_tools(self) -> List:
        """Setup tools for the calculator tool"""

        @tool
        def estimate_total_hotel_cost(price_per_night: Union[float, str], total_days: Union[float, int]) -> float:
            """Calculate Total Hotel Cost by multiplying price per night and number of days"""
            try:
                p = float(str(price_per_night).replace(",", "").replace("$", "").replace("₹", "").strip())
                d = float(total_days)
                return p * d
            except Exception:
                return 0.0

        @tool
        def calculate_total_cost(costs: Union[List[float], float]) -> float:
            """Calculate Total Expense of the trip by summing a list of item costs"""
            try:
                if isinstance(costs, (int, float)):
                    return float(costs)
                if isinstance(costs, list):
                    return sum(float(c) for c in costs if c is not None)
                return 0.0
            except Exception:
                return 0.0

        @tool
        def calculate_daily_expense_budget(total_cost: Union[float, int], days: int) -> float:
            """Calculate daily budget from total cost and total days"""
            try:
                tc = float(total_cost)
                d = int(days)
                return self.calculator.calculate_daily_budget(tc, d)
            except Exception:
                return 0.0

        return [estimate_total_hotel_cost, calculate_total_cost, calculate_daily_expense_budget]