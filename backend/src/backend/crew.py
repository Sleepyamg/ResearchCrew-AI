from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from backend.tools.web_search import web_search

@CrewBase

class ResearchCrew():
    """ResearchCrew-AI: milestone 1 - a single researcher agent."""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"], 
            tools=[web_search],
            verbose=True,
            max_iter=5
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],  
            output_file="output/research_brief.md",
        )

    @crew
    def crew(self) -> Crew:
        """Creates the research crew."""
        return Crew(
            agents=self.agents,  
            tasks=self.tasks,   
            process=Process.sequential,
            verbose=True,
        )
