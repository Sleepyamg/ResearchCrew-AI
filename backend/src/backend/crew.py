from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent


@CrewBase
class ResearchCrew():
    """ResearchCrew-AI: milestone 1 - a single researcher agent."""

    agents: list[BaseAgent]
    tasks: list[Task]

    # Paths are relative to this file. @CrewBase loads them into
    # self.agents_config / self.tasks_config as dicts keyed by the YAML names.
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        # No `llm=` here: CrewAI falls back to MODEL from .env (OpenRouter).
        # No `tools=` yet: this agent answers from the model's own knowledge.
        # Real web search is the next milestone.
        return Agent(
            config=self.agents_config["researcher"],  # type: ignore[index]
            verbose=True,
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],  # type: ignore[index]
            output_file="output/research_brief.md",
        )

    @crew
    def crew(self) -> Crew:
        """Creates the research crew."""
        return Crew(
            agents=self.agents,  # filled automatically by the @agent methods
            tasks=self.tasks,    # filled automatically by the @task methods
            process=Process.sequential,
            verbose=True,
        )
