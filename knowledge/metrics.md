# Traffic Simulation Metrics

## average_queue

Definition:

At each simulation step, sum the number of halting vehicles over all monitored approach lanes. Then average this total queue over all simulation steps.

Unit:

veh

Interpretation:

This is the time-average total queue over the monitored approach lanes.

It is NOT the average queue per lane.


## mean_network_waiting_time

Definition:

At each simulation step, sum the current waiting time of all vehicles on the monitored approach lanes. Then average this summed waiting-time state over all simulation steps.

Unit:

s

Interpretation:

This is a time-average network-level waiting-time state over the monitored approach lanes.

It is NOT the average waiting time per vehicle.


## mean_vehicle_waiting_time

Definition:

For every vehicle observed on the monitored approach lanes during the observation window, accumulate the time that the vehicle is in a waiting state while it is on those monitored lanes.

Then calculate:

total_vehicle_waiting_time / observed_vehicle_count

Unit:

s/veh

Vehicles that are still unfinished at the end of the simulation are included if they were observed on the monitored lanes.

This is NOT the complete trip waitingTime.


## throughput

Definition:

The cumulative number of vehicles that arrived at their destination during the simulation observation window.

Unit:

veh


## completion_rate

Definition:

total_arrived / total_departed

Interpretation:

This is a finite-horizon completion indicator.