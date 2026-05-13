from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from search_tools import web_search , scrape_url 
from dotenv import load_dotenv
from config import MODEL_NAME
import os

load_dotenv()

# Use a dedicated API key for the research pipeline to avoid sharing
# the 8000 TPM limit with the coding pipeline.
_research_api_key = os.getenv("GROQ_API_KEY_RESEARCH") or os.getenv("GROQ_API_KEY")

#model setup 
llm = ChatGroq(model=MODEL_NAME, temperature=0, api_key=_research_api_key)


#1st agent 
def build_search_agent():
    return create_react_agent(
        model = llm,
        tools= [web_search]
    )

#2nd agent 

def build_reader_agent():
    return create_react_agent(
        model = llm,
        tools = [scrape_url]
    )


#writer chain 

writer_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert research writer. Write clear, structured and concise reports."),
    ("human", """Write a research report on the topic below.

Topic: {topic}

Research Gathered:
{research}

Structure the report as:
- Introduction (2-3 sentences)
- Key Findings (3 points, 2-3 sentences each)
- Conclusion (2-3 sentences)
- Sources (list URLs found in the research)

Be factual and professional. Keep the total report under 400 words."""),
])

writer_chain = writer_prompt | llm | StrOutputParser()

#critic_chain 

critic_prompt = ChatPromptTemplate.from_messages([
     ("system", "You are a sharp and constructive research critic. Be honest and specific."),
    ("human", """Review the research report below and evaluate it strictly.

Report:
{report}

Respond in this exact format:

Score: X/10

Strengths:
- ...
- ...

Areas to Improve:
- ...
- ...

One line verdict:
..."""),
])

critic_chain = critic_prompt | llm | StrOutputParser()

