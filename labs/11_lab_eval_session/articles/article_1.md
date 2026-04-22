# 'World Models,' an Old Idea in AI, Mount a Comeback

**Source**: Quanta Magazine  
**Author**: John Pavlus  
**Date**: September 2, 2025

---

The latest ambition of artificial intelligence research — particularly within the labs seeking "artificial general intelligence," or AGI — is something called a world model: a representation of the environment that an AI carries around inside itself like a computational snow globe. The AI system can use this simplified representation to evaluate predictions and decisions before applying them to its real-world tasks. The deep learning luminaries Yann LeCun (of Meta), Demis Hassabis (of Google DeepMind) and Yoshua Bengio (of Mila, the Quebec Artificial Intelligence Institute) all believe world models are essential for building AI systems that are truly smart, scientific and safe.

The fields of psychology, robotics and machine learning have each been using some version of the concept for decades. You likely have a world model running inside your skull right now — it's how you know not to step in front of a moving train without needing to run the experiment first.

So does this mean that AI researchers have finally found a core concept whose meaning everyone can agree upon? As a famous physicist once wrote: Surely you're joking. A world model may sound straightforward — but as usual, no one can agree on the details. What gets represented in the model, and to what level of fidelity? Is it innate or learned, or some combination of both? And how do you detect that it's even there at all?

## Historical Origins

It helps to know where the whole idea started. In 1943, a dozen years before the term "artificial intelligence" was coined, a 29-year-old Scottish psychologist named Kenneth Craik published an influential monograph in which he mused that "if the organism carries a 'small-scale model' of external reality … within its head, it is able to try out various alternatives, conclude which is the best of them … and in every way to react in a much fuller, safer, and more competent manner." Craik's notion of a mental model or simulation presaged the "cognitive revolution" that transformed psychology in the 1950s and still rules the cognitive sciences today. What's more, it directly linked cognition with computation: Craik considered the "power to parallel or model external events" to be "the fundamental feature" of both "neural machinery" and "calculating machines."

The nascent field of artificial intelligence eagerly adopted the world-modeling approach. In the late 1960s, an AI system called SHRDLU wowed observers by using a rudimentary "block world" to answer commonsense questions about tabletop objects, like "Can a pyramid support a block?" But these handcrafted models couldn't scale up to handle the complexity of more realistic settings. By the late 1980s, the AI and robotics pioneer Rodney Brooks had given up on world models completely, famously asserting that "the world is its own best model" and "explicit representations … simply get in the way."

## The Deep Learning Revival

It took the rise of machine learning, especially deep learning based on artificial neural networks, to breathe life back into Craik's brainchild. Instead of relying on brittle hand-coded rules, deep neural networks could build up internal approximations of their training environments through trial and error and then use them to accomplish narrowly specified tasks, such as driving a virtual race car. In the past few years, as the large language models behind chatbots like ChatGPT began to demonstrate emergent capabilities that they weren't explicitly trained for — like inferring movie titles from strings of emojis, or playing the board game Othello — world models provided a convenient explanation for the mystery. To prominent AI experts such as Geoffrey Hinton, Ilya Sutskever and Chris Olah, it was obvious: Buried somewhere deep within an LLM's thicket of virtual neurons must lie "a small-scale model of external reality," just as Craik imagined.

## The Reality: Bags of Heuristics

The truth, at least so far as we know, is less impressive. Instead of world models, today's generative AIs appear to learn "bags of heuristics": scores of disconnected rules of thumb that can approximate responses to specific scenarios, but don't cohere into a consistent whole. (Some may actually contradict each other.) It's a lot like the parable of the blind men and the elephant, where each man only touches one part of the animal at a time and fails to apprehend its full form. One man feels the trunk and assumes the entire elephant is snakelike; another touches a leg and guesses it's more like a tree; a third grasps the elephant's tail and says it's a rope. When researchers attempt to recover evidence of a world model from within an LLM — for example, a coherent computational representation of an Othello game board — they're looking for the whole elephant. What they find instead is a bit of snake here, a chunk of tree there, and some rope.

Of course, such heuristics are hardly worthless. LLMs can encode untold sackfuls of them within their trillions of parameters — and as the old saw goes, quantity has a quality all its own. That's what makes it possible to train a language model to generate nearly perfect directions between any two points in Manhattan without learning a coherent world model of the entire street network in the process, as researchers from Harvard University and the Massachusetts Institute of Technology recently discovered.

## Why World Models Matter

So if bits of snake, tree and rope can do the job, why bother with the elephant? In a word, robustness: When the researchers threw their Manhattan-navigating LLM a mild curveball by randomly blocking 1% of the streets, its performance cratered. If the AI had simply encoded a street map whose details were consistent — instead of an immensely complicated, corner-by-corner patchwork of conflicting best guesses — it could have easily rerouted around the obstructions.

Given the benefits that even simple world models can confer, it's easy to understand why every large AI lab is desperate to develop them — and why academic researchers are increasingly interested in scrutinizing them, too. Robust and verifiable world models could uncover, if not the El Dorado of AGI, then at least a scientifically plausible tool for extinguishing AI hallucinations, enabling reliable reasoning, and increasing the interpretability of AI systems.

## The Path Forward

That's the "what" and "why" of world models. The "how," though, is still anyone's guess. Google DeepMind and OpenAI are betting that with enough "multimodal" training data — like video, 3D simulations, and other input beyond mere text — a world model will spontaneously congeal within a neural network's statistical soup. Meta's LeCun, meanwhile, thinks that an entirely new (and non-generative) AI architecture will provide the necessary scaffolding. In the quest to build these computational snow globes, no one has a crystal ball — but the prize, for once, may just be worth the hype.
