
import os

from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task

from backend.tools.web_search import web_search
from backend.tools.web_scraper import web_scraper


# Load environment variables
load_dotenv()


# Configure the LLM
llm = LLM(
    model=os.getenv("MODEL"),
    api_key=os.getenv("OPENROUTER_API_KEY"),
    context_window_size=32768,
    temperature=0.2
)


@CrewBase
class ResearchCrew:
    """Hierarchical multi-agent research system."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # ==============================
    # Agents
    # ==============================

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            llm=llm,
            tools=[
                web_search,
                web_scraper
            ],
            allow_delegation=False,
            verbose=True,
            max_iter=10
        )

    @agent
    def fact_checker(self) -> Agent:
        return Agent(
            config=self.agents_config["fact_checker"],
            llm=llm,
            tools=[
                web_search,
                web_scraper
            ],
            allow_delegation=False,
            verbose=True,
            max_iter=8
        )

    @agent
    def report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["report_writer"],
            llm=llm,
            allow_delegation=False,
            verbose=True,
            max_iter=3
        )

    # ==============================
    # Tasks
    # ==============================

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"]
        )

    @task
    def verification_task(self) -> Task:
        return Task(
            config=self.tasks_config["verification_task"],
            context=[self.research_task()]
        )

    @task
    def report_task(self) -> Task:
        return Task(
            config=self.tasks_config["report_task"],
            context=[self.verification_task()]
        )

    # ==============================
    # Crew and Research Manager
    # ==============================

    @crew
    def crew(self) -> Crew:

        manager = Agent(
            config=self.agents_config["research_manager"],
            llm=llm,
            allow_delegation=True,
            verbose=True,
            max_iter=8
        )

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            manager_agent=manager,
            process=Process.hierarchical,
            verbose=True
        )
