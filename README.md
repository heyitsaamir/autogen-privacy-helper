## Readme

This is a simple project that demonstrates the use of [autogen](https://github.com/microsoft/autogen) in the context of a Microsoft Teams AI bot.
This bot models privacy review helper. The team consists of:
1. A questioner agent - the role of this agent is to ask questions based on some criteria for evaluating a threat model
2. An answerer agent - the role of this agent is to answer the questions asked by the questioner agent based on an image of the threat model (currently using gpt4-v)
3. An evaluator agent - the role of this agent is to evaluate the answers given by the answerer agent based on the criteria given by the questioner agent.

The result from the evaluator agent is sent back to the Teams user. We also send back an adaptive card that contains the full transcript of the back-and-forth beteween the agents.