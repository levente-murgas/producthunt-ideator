from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: str
    status: str


class RunWorkflowIn(BaseModel):
    # date should be in the format of "YYYY-MM-DD"
    date: str = Field(
        description="Date of the workflow, format: YYYY-MM-DD",
        default=datetime.today().strftime("%Y-%m-%d"),
    )


class Proposal(BaseModel):
    title: str = Field(description="Title of the proposal")
    description: str = Field(description="Description of the proposal")


class Analysis(BaseModel):
    strengths: str = Field(description="Strengths of the current product")
    weaknesses: str = Field(description="Weaknesses of the current product")
    proposals: List[Proposal] = Field(description="List of new proposals")

    def to_markdown(self) -> str:
        proposals = "\n".join([f"- {p.title}: {p.description}" for p in self.proposals])
        return f"""
## Product analysis:\n

### Strengths:\n
{self.strengths}

### Weaknesses:\n
{self.weaknesses}

### Proposals\n
{proposals}""".format(
            proposals=proposals,
        )
