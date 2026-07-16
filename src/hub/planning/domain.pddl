; greenhouse-domain.pddl
; Intelligent Autonomous Greenhouse — Group 26
; Smart Cities & IoT, University of Stuttgart, Summer 2026
;
; Run with Fast Downward (cost-optimal A* + LM-Cut heuristic):
;   fast-downward domain.pddl problem.pddl --search "astar(lmcut())"
;
; ----------------------------------------------------------------------------
; HARDWARE THIS DOMAIN MODELS
; ----------------------------------------------------------------------------
;   Plant ESP (x2, one per plant, node-plant*):
;     - soil moisture sensor   -> (soil-dry ?p)
;     - water pump actuator    -> irrigate ?p / deactivate-pump ?p
;
;   Greenhouse ESP (x1, node-greenhouse):
;     - DHT11 temperature      -> (temp-high)
;     - DHT11 humidity         -> (humidity-high)
;     - MQ135 CO2              -> (co2-high)
;     - ultrasonic tank level  -> (tank-low)
;     - grow light actuator    -> activate-light / deactivate-light
;     - PWM fan actuator       -> activate-fan  / deactivate-fan
;
;   Weather API (virtual sensor, published on virtual/weather):
;     - cloud cover / daylight -> (light-needed)   drives the grow light
;     - hot forecast           -> tightens the moisture threshold in the
;                                 Problem Generator (NOT a domain predicate)
;     (The greenhouse has a fixed, non-opening lid, so rainfall never reaches
;      the soil. Rain probability is therefore irrelevant to irrigation and is
;      not modelled.)
;
;   Human actuator:
;     - refill water tank      -> refill-tank  (web UI alert)
;
; ----------------------------------------------------------------------------
; ACTION -> MQTT COMMAND MAPPING (handled by hub/planning/executor.py)
; ----------------------------------------------------------------------------
; Plant objects ?p are node ids, so plans read e.g. (irrigate node-plant1).
;
;   irrigate ?p      -> nodes/<?p>/command             pump = true
;                       (a timed dose: the plant firmware stops the pump by
;                        itself after PUMP_RUN_MS; the hub re-sends the dose
;                        each cycle while the soil stays dry)
;   deactivate-pump  -> nodes/<?p>/command             pump = false
;   activate-light   -> nodes/<greenhouse>/command     led  = true
;   deactivate-light -> nodes/<greenhouse>/command     led  = false
;   activate-fan     -> nodes/<greenhouse>/command     fan  = true
;   deactivate-fan   -> nodes/<greenhouse>/command     fan  = false
;   refill-tank      -> planning/alert                 web UI alert (human)
;
; The fan is PWM, but for planning it is treated as on/off; the Plan Executor
; chooses the duty cycle when it dispatches the command.
;
; Problem files are generated automatically by the Problem Generator
; (hub/planning/problem_generator.py) from the hub's latest-per-topic
; snapshot whenever the induced facts change. You do not edit the problem
; file by hand.

(define (domain greenhouse)

  (:requirements :strips :typing :action-costs
                 :negative-preconditions :disjunctive-preconditions)

  ;; Only the plants are typed objects. Everything else (temperature, humidity,
  ;; CO2, light, fan, tank) is greenhouse-wide, so it is modelled with
  ;; parameter-free predicates.
  (:types plant)

  (:predicates
    ;; ---- per-plant care conditions ----------------------------------------
    (soil-dry     ?p - plant)   ; moisture sensor below configured threshold
    (pump-active  ?p - plant)   ; this plant's pump is currently running

    ;; ---- greenhouse-wide care conditions ----------------------------------
    (temp-high)                 ; DHT11 temperature above threshold
    (humidity-high)             ; DHT11 humidity above threshold
    (co2-high)                  ; MQ135 CO2 above threshold
    (light-needed)              ; weather API: cloudy / outside daylight hours
    (tank-low)                  ; ultrasonic: tank level below minimum

    ;; ---- greenhouse-wide actuator states ----------------------------------
    (light-active)
    (fan-active)
  )

  ;; total-cost is the optimisation metric — a proxy for energy consumption.
  ;; Costs are relative to the average power draw of each actuator.
  (:functions (total-cost))


  ;; =========================================================================
  ;; Irrigation  (per plant)
  ;; =========================================================================

  ;; Start a timed watering dose (the firmware stops the pump on its own).
  ;; Blocked only when the tank is empty.
  (:action irrigate
    :parameters  (?p - plant)
    :precondition (and (soil-dry ?p)
                       (not (tank-low)))
    :effect       (and (not (soil-dry ?p))
                       (pump-active ?p)
                       (increase (total-cost) 3))
  )

  ;; Rare cleanup only: the firmware ends every dose itself, so this fires
  ;; just when a snapshot happens to catch a pump mid-dose on soil that is
  ;; no longer dry.
  (:action deactivate-pump
    :parameters  (?p - plant)
    :precondition (pump-active ?p)
    :effect       (and (not (pump-active ?p))
                       (increase (total-cost) 0))
  )


  ;; =========================================================================
  ;; Lighting  (greenhouse-wide, driven by the weather API)
  ;; =========================================================================

  (:action activate-light
    :parameters  ()
    :precondition (light-needed)
    :effect       (and (not (light-needed))
                       (light-active)
                       (increase (total-cost) 2))
  )

  (:action deactivate-light
    :parameters  ()
    :precondition (light-active)
    :effect       (and (not (light-active))
                       (increase (total-cost) 0))
  )


  ;; =========================================================================
  ;; Ventilation  (greenhouse-wide PWM fan)
  ;; =========================================================================

  ;; One fan addresses three conditions at once — ventilation lowers
  ;; temperature, humidity and CO2 simultaneously. The disjunctive
  ;; precondition lets the planner fire the fan when ANY of the three holds;
  ;; the effect clears all three (deleting a fact that is already false is a
  ;; harmless no-op). Cost is therefore counted only once.
  (:action activate-fan
    :parameters  ()
    :precondition (and (not (fan-active))
                       (or (temp-high) (humidity-high) (co2-high)))
    :effect       (and (not (temp-high))
                       (not (humidity-high))
                       (not (co2-high))
                       (fan-active)
                       (increase (total-cost) 2))
  )

  (:action deactivate-fan
    :parameters  ()
    :precondition (fan-active)
    :effect       (and (not (fan-active))
                       (increase (total-cost) 0))
  )


  ;; =========================================================================
  ;; Water tank — HUMAN ACTUATOR
  ;; =========================================================================

  ;; Not sent to an ESP. The Plan Executor publishes to planning/alert,
  ;; raising an alert in the web dashboard asking a human to refill the tank,
  ;; and defers the plan's irrigate steps (the only actions that depend on
  ;; the tank). Once the ultrasonic sensor reads above the minimum again the
  ;; next planning cycle no longer asserts (tank-low) and irrigation proceeds.
  (:action refill-tank
    :parameters  ()
    :precondition (tank-low)
    :effect       (and (not (tank-low))
                       (increase (total-cost) 1))
  )

)
