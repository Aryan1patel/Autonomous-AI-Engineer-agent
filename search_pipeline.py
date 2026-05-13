import time
from groq import APIStatusError
from search_agents import build_reader_agent , build_search_agent , writer_chain , critic_chain

def _invoke_with_retry(chain_or_agent, inputs: dict, label: str = "llm"):
    """Invoke a chain/agent with automatic retry on Groq 413 rate-limit errors."""
    for attempt in range(1, 6):
        try:
            return chain_or_agent.invoke(inputs)
        except APIStatusError as e:
            if e.status_code == 413 and attempt < 6:
                wait = 15 * attempt
                print(f"[{label}] Rate limit hit. Waiting {wait}s before retry {attempt}/5...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"{label}: exceeded rate-limit retries")

def run_research_pipeline(topic : str) -> dict:

    state = {}

    #search agent working 
    print("\n"+" ="*50)
    print("step 1 - search agent is working ...")
    print("="*50)

    search_agent = build_search_agent()
    search_result = _invoke_with_retry(search_agent, {
        "messages" : [("user", f"Find recent, reliable and detailed information about: {topic}")]
    }, "search_agent")
    state["search_results"] = search_result['messages'][-1].content[:2000]

    print("\n search result ",state['search_results'])

    #step 2 - reader agent 
    print("\n"+" ="*50)
    print("step 2 - Reader agent is scraping top resources ...")
    print("="*50)

    reader_agent = build_reader_agent()
    reader_result = _invoke_with_retry(reader_agent, {
        "messages": [("user",
            f"Based on the following search results about '{topic}', "
            f"pick the most relevant URL and scrape it for deeper content.\n\n"
            f"Search Results:\n{state['search_results'][:800]}"
        )]
    }, "reader_agent")

    state['scraped_content'] = reader_result['messages'][-1].content[:2000]

    print("\nscraped content: \n", state['scraped_content'])

    #step 3 - writer chain 

    print("\n"+" ="*50)
    print("step 3 - Writer is drafting the report ...")
    print("="*50)

    research_combined = (
        f"SEARCH RESULTS : \n {state['search_results'][:1500]} \n\n"
        f"DETAILED SCRAPED CONTENT : \n {state['scraped_content'][:1500]}"
    )

    state["report"] = _invoke_with_retry(writer_chain, {
        "topic" : topic,
        "research" : research_combined
    }, "writer_chain")

    print("\n Final Report\n",state['report'])

    #critic report 

    print("\n"+" ="*50)
    print("step 4 - critic is reviewing the report ")
    print("="*50)

    state["feedback"] = _invoke_with_retry(critic_chain, {
        "report":state['report']
    }, "critic_chain")

    print("\n critic report \n", state['feedback'])

    return state



if __name__ == "__main__":
    topic = input("\n Enter a research topic : ")
    run_research_pipeline(topic)

