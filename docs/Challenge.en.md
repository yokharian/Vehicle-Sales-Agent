# AI Sales Agent

The project involves developing a bot that leverages large language models (LLMs) to simulate the behavior of a Kavak sales agent. The bot must be made available via an API in Python or Go.

Evaluation will be based on pragmatism, the ability to structure the problem, the proposed solution, best development practices, the ability to prioritize, and creativity. Completeness is not a factor in the evaluation.

## The sales bot must have the following capabilities

- Provide basic information about Kavak’s value proposition.
- Minimize hallucinations within the chatbot as much as possible.
- The chatbot must be able to handle the complexities of using natural language for interaction (e.g., errors in the user’s description of the make and model).
- Provide recommendations for available cars from the catalog based on the customer’s preferences.
- Offer financing plans based on the down payment, the car’s price, a 10% interest rate, and financing terms ranging from 3 to 6 years.

## For this assignment, we expect the following deliverables

- A live demo of the bot connected to WhatsApp (as a hint, you can create a Twilio account and use the sandbox).
- A high-level diagram of the components and architecture.
- A diagram of prompts, agent architecture, and tools, if applicable.
- Python or Go code for the bot.
- A proposed roadmap and backlog for deploying this bot to production. Some of the questions this roadmap should address are:
  - How would you deploy this to production?
  - How would you evaluate the agent’s performance?
  - How would you test that a new version of the agent does not introduce any regression in its functionality?

Be as creative as you like; remember that the ultimate goal is to develop a bot that mimics a sales agent. Feel free to propose any solution that helps you achieve this goal.

You can create different versions of the bot; it’s not necessary to develop all the listed capabilities—just make sure you can meet the exercise’s deliverables. You’ll earn bonus points if your development ensures reproducibility—that is, if you create a manual that allows anyone to install your bot.

## Resources

- Kavak's value proposition (uses the information on this page):
<https://www.kavak.com/mx/blog/sedes-de-kavak-en-mexico>
- Temporary OpenAI API key:
sk-proj-...
- Sample CSV for the catalog (attached to the email).

*Please note that this API key has a rate limit of 50,000 tokens per minute and only has access to the default versions of gpt-3.5-turbo, gpt-4-turbo, and gpt-4o.
