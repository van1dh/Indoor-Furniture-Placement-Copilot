# Indoor-Furniture-Placement-Copilot

## Reminder: This is the demonstration page. All frontend & backend code is on master branch.

## Introduction

Nowadays, as homes become more intelligent and personalized, optimizing space for both aesthetics and functionality is becoming an essential part of modern living. With the assistance of machine learning and co-pilot technologies, it’s possible to get suggestions for ideal furniture layouts based on real-life data such as activity patterns. The indoor furniture placement copilot project utilizes AI and machine learning to create a tool that can give furniture placement plans based on safety and comfort.

## Members

Yongyi Xie xyy0208@bu.edu

## User Stories
### User Story 1: Child-Safe Room Design for Parents
	A mother wants to make her living room safe for her toddler, ensuring that sharp or fragile furniture is kept out of the child’s reach. She seeks help from the furniture placement copilot to suggest an arrangement that leaves ample space for her child to play without tripping hazards.
### User Story 2: Accessible Bedroom for Mobility-Impaired Adults
	A wheelchair user needs a bedroom layout that provides easy access to the bed, closet, and desk, with enough space to maneuver the wheelchair. The copilot assists in rearranging furniture to optimize accessibility while maintaining functionality.
### User Story 3: Shared Space Optimization for Tenants
	A group of four students, two boys, and two girls, live in one studio, with boys needing space to play together, girls gossiping together, and everyone getting privacies. They also need some space for group work. They want the furniture arranged to accommodate everyone’s needs without making the space feel cramped or chaotic.
## Recent Progress
10/14: Data Generation completed in main.py. The sample output is in path.json, in the format of [start_time_since_00:00_in_seconds, x_position_in_feet, y_position_in_feet]. The original point starts from the bottom-left corner of the room, which is a rectangle.
In main.py, furniture and people classes are defined. Details are included in the file.

11/7: Path and room Layout Visualizations. Given input furniture numbers, the program can output a basic design, ensuring they don't collide.

Express.js creation. This involves creating the backend part. Using node.js, I implemented a call for OpenAI API and made a local server.

11/25: Javascript + CSS implementation of front-end design. Established the structure of three pages, WelcomePage, Generation Page and Result Page.
I use React package to implement the frame. All codes in master branch.

12/5: Connect frontend (on localhost:3000) to backend (on localhost:5000/api/generate), and go through unit testing.

## What To Do In Further Improvments
Add ways to modify the furniture sizes and room size by user themselves.

Adjust the generation style to look more vivid.

Further improve user interface (UI) for better user experiences based on feedbacks.

## References
[1] L. Yanhua, “Optimizing Space with AI: Intelligent Design Solutions for Soft Furnishings and Decor,” International Journal of Science and Engineering Applications, vol. 13, no. 7, Jun. 2024, doi: https://doi.org/10.7753/ijsea1307.1008

[2] S. I. Mohamed, M. M. Saady, and Z. A. E. H. Taha, “Virtual Utopia: AI-Enhanced 3D Room Design Simulation for Optimal Furniture Layout,” 2024 Intelligent Methods, Systems, and Applications (IMSA), pp. 489–494, Jul. 2024, doi: https://doi.org/10.1109/imsa61967.2024.10652795

[3] A. Penn and A. Turner, “Space layout affects search efficiency for agents with vision,” 2003. Available: https://www.spacesyntax.net/symposia-archive/SSS4/fullpapers/09Penn-Turner.pdf. [Accessed: Oct. 01, 2024]

[4] K. G., “Layout design for efficiency improvement and cost reduction,” Bulletin of the Polish Academy of Sciences: Technical Sciences, 2019, doi: https://doi.org/10.24425/bpasts.2019.129653. Available: https://journals.pan.pl/dlibra/publication/129653/edition/113167/content

[5] M. Ran and J. Dong, “A Multiobjective Optimization Algorithm for Building Interior Design and Spatial Structure Optimization,” Mobile Information Systems, 	vol. 2022, pp. 1–15, Jul. 2022, doi: https://doi.org/10.1155/2022/5659280

[6] L. Chen, C. Nugent, and G. Okeyo, “An Ontology-Based Hybrid Approach to Activity Modeling for Smart Homes,” IEEE Transactions on Human-Machine Systems, vol. 44, no. 1, pp. 92–105, Feb. 2014, doi: 	https://doi.org/10.1109/thms.2013.2293714tion,” Mobile Information Systems, 	vol. 2022, pp. 1–15, Jul. 2022, doi: https://doi.org/10.1155/2022/5659280

[7] L. Chen, C. Nugent, and G. Okeyo, “An Ontology-Based Hybrid Approach to Activity Modeling for Smart Homes,” IEEE Transactions on Human-Machine Systems, vol. 44, no. 1, pp. 92–105, Feb. 2014, doi: 	https://doi.org/10.1109/thms.2013.2293714
