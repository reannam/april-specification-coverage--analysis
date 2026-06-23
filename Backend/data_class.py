from pydantic import BaseModel, Field
from typing import Literal

class VPlanColumns(BaseModel):
    test_id: str = Field(..., description="Unique test ID, e.g. TEST_REQ_I2C_001")
    requirement_id: str = Field(..., description="The exact requirement ID from the input JSON")
    test_type: Literal["positive", "negative"] = Field(..., description="The type of test")
    test_description: str = Field(..., description="The description of the test")
    test_description: str = Field(..., description="What is being tested")
    test_constraints: str = Field(..., description="Constraints, preconditions, or 'None specified'")
    test_steps: list[str] = Field(..., description="Concrete verification steps")
    expected_results: list[str] = Field(..., description="Expected observable results")
    priority: Literal[1, 2, 3] = Field(..., description="1 = high, 2 = medium, 3 = low")
    coverage: Literal["covered", "partially_covered", "blocked"] = Field(..., description="Coverage status of the requirement")



class Table(BaseModel):
   feature_list: list[VPlanColumns] = Field(..., description="Rows of vPlan table")
