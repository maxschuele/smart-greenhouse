# Smart Cities and Internet of Things | Course Project

## Context

Masters university computer science project for a course on "Smart Cities and Internet of Things"

TODO: more context

Design and implementation of a system within the specified context and focus

## Project Requirements

1. System distribution
	- 2+ machines
2. System integration
	-  Indirect communication between components (e.g., publish-subscribe, message queues)
3. AI planning
	- Domain model
	- Problem instances (automatically generated)
	- Usage of suitable AI planner
4. IoT
	- 4+ sensors and
	- 4+ actuators
		- (2+) physical + (2+) software-based, human-based, simulated, or virtual
5. System design
	- Modularity of system components (e.g., IoT, processing, problem generation, planning, execution)
6. Visualisation contains at least
	- Current state of the environment
	- The latest plan (being) executed

## Project Proposal

### Modular Smart Buildings Framework

Build wireless sensor/actuator nodes using ESP32 that communicate over a custom MQTT protocol to a Central Control Node/Hub. 
The main goal here is to build a modular adaptive system. 

Goal in the long run:
- AI Planning Model, can adapt to different sensor and sensor positions

**Goals**
- lightweight
- modular
	- easy to extend with aditionals sensors & actuators
	- sensors/actuators can dynamically join and leave the system
-  AI Planning
	- TODO

**Node Types**
- ESP32 (or other micro controller that has wifi & supports MQTT)
	- sensor nodes
	- actuator nodes
	- sensor + actuator nodes
- central control node on raspberry pi

**Stack**
- MQTT
	- sensor/actuator nodes send advertisement packages
		- can dynamicaly join/leave the sysstem
	- Generic Message Protocol
		- can be adapted to new nodes
- Central control node (raspberry pi)
	- MQTT hub
		- python with [aiomqtt](https://pypi.org/project/aiomqtt/)
		- broker https://mosquitto.org/ https://hub.docker.com/_/eclipse-mosquitto
		- collects sensor data from MQTT
			- needs a db(?)
		- send commands via mqtt
	- API (fastapi, python, js) 
		- Dashboard with Chart.js
		- Discord Chatbot using the REST API
	- hub & api as one or seprate processes?
- AI Planing
    - TODO: needs further information/research
	- ignore for now
