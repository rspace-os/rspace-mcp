## Example use cases

RSpace MCP enables conversational interaction with AI agents to invoke tools in pursuit of a goal. This document is to suggest some initial use-cases and to stimulate imagination of what's possible. 

### Prompts
Here are some basic prompts:

1. Can you get the audit log from RSpace for the last 2 weeks, and output a table showing how many new documents were created by each user
2. Can you get my last 10 documents and tag them with 'mytag'
3. Can you get all my documents created in the last 3 weeks and tell me which ones aren't signed

### Combining RSpace MCP with other MCP servers
When combined with other MCP servers such as `email`, `pubmed` and `filesystem`, much more complex workflows are possible: 

1. Can you do a pubmed search for review of p53 inhibitors published in 2025. Create a new notebook called 'Pubmed-July2025' and add a new entry with links and abstracts of the pubmed search. Email my boss boss@lab.ac.uk with a link to the notebook.
2. Can you download all the images  from all entries in  notebook NB12345,  and put them in folder 'my-images'
