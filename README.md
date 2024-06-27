## Readme

This is a simple project that demonstrates the use of [autogen](https://github.com/microsoft/autogen) in the context of a Microsoft Teams AI bot.
This bot models privacy review helper. The team consists of:
1. A questioner agent - the role of this agent is to ask questions based on some criteria for evaluating a threat model
2. An answerer agent - the role of this agent is to answer the questions asked by the questioner agent based on an image of the threat model (currently using gpt4-v)
3. An evaluator agent - the role of this agent is to evaluate the answers given by the answerer agent based on the criteria given by the questioner agent.

The result from the evaluator agent is sent back to the Teams user. We also send back an adaptive card that contains the full transcript of the back-and-forth beteween the agents.

![alt text](docs/image.png)

## How to run the project
This project uses Teams AI library and autogen.

### Prerequisites
1. Install the Teams Toolkit extension for Visual Studio Code - [Link](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/teams-toolkit-fundamentals)
2. Setup your virtual env (`virtualenv .venv` and `source .venv/bin/activate`)

### Steps
1. Clone repo
2. Install the required packages. I used poetry to manage the dependencies. You can install poetry by running `pip install poetry`. Then run `poetry install` to install the dependencies.
3. Update .env. Make sure it includes either `OPENAI_KEY` or `AZURE_OPENAI_API_KEY` with `AZURE_OPENAI_ENDPOINT`. If you look for `build_llm_config` in the code, you will see how it builds the config for the model.
3. Open the project in VSCode. Make sure you have the Teams Toolkit (TTK) extension installed.
5. Go to the TTK extension, then click "local" debug under environment. This will create a package under appPackage/build folder and start Teams up. It'll also do the installation for your bot on Teams.