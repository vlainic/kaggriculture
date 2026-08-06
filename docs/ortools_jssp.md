# The Job Shop Problem

One common scheduling problem is the *job shop*, in which multiple jobs are
processed on several machines.

Each job consists of a sequence of tasks, which must be performed in a given
order, and each task must be processed on a specific machine.
For example, the job could be the manufacture of a single consumer item, such as
an automobile.
The problem is to schedule the tasks on the machines so as to minimize the
`length` of the schedule---the time it takes for all the jobs to be completed.

There are several constraints for the job shop problem:

- No task for a job can be started until the previous task for that job is completed.
- A machine can only work on one task at a time.
- A task, once started, must run to completion.

## Example Problem

Below is a simple example of a job shop problem, in which each task is labeled
by a pair of numbers (m, p) where m is the number of the machine the task
must be processed on and p is the *processing time* of the task --- the
amount of time it requires. (The numbering of jobs and machines starts at 0.)

- job 0 = \[(0, 3), (1, 2), (2, 2)\]
- job 1 = \[(0, 2), (2, 1), (1, 4)\]
- job 2 = \[(1, 4), (2, 3)\]

In the example, job 0 has three tasks. The first, (0, 3), must be processed
on machine 0 in 3 units of time. The second, (1, 2), must be processed on
machine 1 in 2 units of time, and so on. Altogether, there are eight tasks.

### A solution for the problem

A solution to the job shop problem is an assignment of a start time for each
task, which meets the constraints given above.
The diagram below shows one possible solution for the problem:

![timeline of suboptimal jobshop schedule](https://developers.google.com/static/optimization/images/scheduling/schedule1.png)

You can check that the tasks for each job are scheduled at non-overlapping time
intervals, in the order given by the problem.

The length of this solution is 12, which is the first time when all three jobs
are complete.
However, as you will see [below](https://developers.google.com/optimization/scheduling/job_shop#output), this is not the optimal solution to
the problem.

### Variables and constraints for the problem

This section describes how to set up the variables and constraints for the
problem.
First, let `task(i, j)` denote the jth task in the sequence for job i. For
example, `task(0, 2)` denotes the second task for job 0, which corresponds to
the pair `(1, 2)` in the problem description.

Next, define *t* ~i, j~ to be the start time for `task(i, j)`. The
*t* ~i, j~ are the variables in the job shop problem. Finding a
solution involves determining values for these variables that meet the
requirement of the problem.

There are two types of constraints for the job shop problem:

- *Precedence constraints* --- These arise from the condition that for any two consecutive tasks in the same job, the first must be completed before the second can be started. For example, `task(0, 2)` and `task(0, 3)` are consecutive tasks for job 0. Since the processing time for `task(0, 2)` is 2, the start time for `task(0, 3)` must be at least 2 units of time after the start time for task 2. (Perhaps task 2 is painting a door, and it takes two hours for the paint to dry.) As a result, you get the following constraint:
  - `t`~0, 2~ + 2 \<= `t`~0, 3~
- *No overlap constraints* --- These arise from the restriction that a machine can't work on two tasks at the same time. For example, task(0, 2) and task(2, 1) are both processed on machine 1. Since their processing times are 2 and 4, respectively, one of the following constraints must hold:
  - `t`~0, 2~ + 2 \<= `t`~2, 1~ (if `task(0, 2)` is scheduled before `task(2, 1)`) or
  - `t`~2, 1~ + 4 \<= `t`~0, 2~ (if `task(2, 1)` is scheduled before `task(0, 2)`).

### Objective for the problem

The objective of the job shop problem is to minimize the **makespan**: the
length of time from the earliest start time of the jobs to the latest end time.

## A Program solution

The following sections describe the main elements of a program that solves the
job shop problem.

### Import the libraries

The following code imports the required library.

### Python

```python
import collections
from ortools.sat.python import cp_model
```

### C++

```c++
#include <stdlib.h>

#include <algorithm>
#include <cstdint>
#include <map>
#include <numeric>
#include <string>
#include <tuple>
#include <vector>

#include "absl/base/log_severity.h"
#include "absl/log/globals.h"
#include "absl/strings/str_format.h"
#include "ortools/base/init_google.h"
#include "ortools/base/logging.h"
#include "ortools/sat/cp_model.h"
#include "ortools/sat/cp_model.pb.h"
#include "ortools/sat/cp_model_solver.h"
```

### Java

```java
import static java.lang.Math.max;

import com.google.ortools.Loader;
import com.google.ortools.sat.CpModel;
import com.google.ortools.sat.CpSolver;
import com.google.ortools.sat.CpSolverStatus;
import com.google.ortools.sat.IntVar;
import com.google.ortools.sat.IntervalVar;
import com.google.ortools.sat.LinearExpr;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;
```

### C#

```c#
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using Google.OrTools.Sat;
```

### Define the data

Next, the program defines the data for the problem.

### Python

```python
jobs_data = [  # task = (machine_id, processing_time).
    [(0, 3), (1, 2), (2, 2)],  # Job0
    [(0, 2), (2, 1), (1, 4)],  # Job1
    [(1, 4), (2, 3)],  # Job2
]

machines_count = 1 + max(task[0] for job in jobs_data for task in job)
all_machines = range(machines_count)
# Computes horizon dynamically as the sum of all durations.
horizon = sum(task[1] for job in jobs_data for task in job)
```

### C++

```c++
using Task = std::tuple<int64_t, int64_t>;  // (machine_id, processing_time)
using Job = std::vector<Task>;
std::vector<Job> jobs_data = {
    {{0, 3}, {1, 2}, {2, 2}},  // Job_0: Task_0 Task_1 Task_2
    {{0, 2}, {2, 1}, {1, 4}},  // Job_1: Task_0 Task_1 Task_2
    {{1, 4}, {2, 3}},          // Job_2: Task_0 Task_1
};

int64_t num_machines = 0;
for (const auto& job : jobs_data) {
  for (const auto& [machine, _] : job) {
    num_machines = std::max(num_machines, 1 + machine);
  }
}

std::vector<int> all_machines(num_machines);
std::iota(all_machines.begin(), all_machines.end(), 0);

// Computes horizon dynamically as the sum of all durations.
int64_t horizon = 0;
for (const auto& job : jobs_data) {
  for (const auto& [_, time] : job) {
    horizon += time;
  }
}
```

### Java

```java
class Task {
  int machine;
  int duration;
  Task(int machine, int duration) {
    this.machine = machine;
    this.duration = duration;
  }
}

final List<List<Task>> allJobs =
    Arrays.asList(Arrays.asList(new Task(0, 3), new Task(1, 2), new Task(2, 2)), // Job0
        Arrays.asList(new Task(0, 2), new Task(2, 1), new Task(1, 4)), // Job1
        Arrays.asList(new Task(1, 4), new Task(2, 3)) // Job2
    );

int numMachines = 1;
for (List<Task> job : allJobs) {
  for (Task task : job) {
    numMachines = max(numMachines, 1 + task.machine);
  }
}
final int[] allMachines = IntStream.range(0, numMachines).toArray();

// Computes horizon dynamically as the sum of all durations.
int horizon = 0;
for (List<Task> job : allJobs) {
  for (Task task : job) {
    horizon += task.duration;
  }
}
```

### C#

```c#
var allJobs =
    new[] {
        new[] {
            // job0
            new { machine = 0, duration = 3 }, // task0
            new { machine = 1, duration = 2 }, // task1
            new { machine = 2, duration = 2 }, // task2
        }
            .ToList(),
        new[] {
            // job1
            new { machine = 0, duration = 2 }, // task0
            new { machine = 2, duration = 1 }, // task1
            new { machine = 1, duration = 4 }, // task2
        }
            .ToList(),
        new[] {
            // job2
            new { machine = 1, duration = 4 }, // task0
            new { machine = 2, duration = 3 }, // task1
        }
            .ToList(),
    }
        .ToList();

int numMachines = 0;
foreach (var job in allJobs)
{
    foreach (var task in job)
    {
        numMachines = Math.Max(numMachines, 1 + task.machine);
    }
}
int[] allMachines = Enumerable.Range(0, numMachines).ToArray();

// Computes horizon dynamically as the sum of all durations.
int horizon = 0;
foreach (var job in allJobs)
{
    foreach (var task in job)
    {
        horizon += task.duration;
    }
}
```

### Declare the model

The following code declares the model for the problem.

### Python

```python
model = cp_model.CpModel()
```

### C++

```c++
CpModelBuilder cp_model;
```

### Java

```java
CpModel model = new CpModel();
```

### C#

```c#
CpModel model = new CpModel();
```

### Define the variables

The following code defines the variables in the problem.

### Python

```python
# Named tuple to store information about created variables.
task_type = collections.namedtuple("task_type", "start end interval")
# Named tuple to manipulate solution information.
assigned_task_type = collections.namedtuple(
    "assigned_task_type", "start job index duration"
)

# Creates job intervals and add to the corresponding machine lists.
all_tasks = {}
machine_to_intervals = collections.defaultdict(list)

for job_id, job in enumerate(jobs_data):
    for task_id, task in enumerate(job):
        machine, duration = task
        suffix = f"_{job_id}_{task_id}"
        start_var = model.new_int_var(0, horizon, "start" + suffix)
        end_var = model.new_int_var(0, horizon, "end" + suffix)
        interval_var = model.new_interval_var(
            start_var, duration, end_var, "interval" + suffix
        )
        all_tasks[job_id, task_id] = task_type(
            start=start_var, end=end_var, interval=interval_var
        )
        machine_to_intervals[machine].append(interval_var)
```

### C++

```c++
struct TaskType {
  IntVar start;
  IntVar end;
  IntervalVar interval;
};

using TaskID = std::tuple<int, int>;  // (job_id, task_id)
std::map<TaskID, TaskType> all_tasks;
std::map<int64_t, std::vector<IntervalVar>> machine_to_intervals;
for (int job_id = 0; job_id < jobs_data.size(); ++job_id) {
  const auto& job = jobs_data[job_id];
  for (int task_id = 0; task_id < job.size(); ++task_id) {
    const auto [machine, duration] = job[task_id];
    std::string suffix = absl::StrFormat("_%d_%d", job_id, task_id);
    IntVar start = cp_model.NewIntVar({0, horizon})
                       .WithName(std::string("start") + suffix);
    IntVar end = cp_model.NewIntVar({0, horizon})
                     .WithName(std::string("end") + suffix);
    IntervalVar interval = cp_model.NewIntervalVar(start, duration, end)
                               .WithName(std::string("interval") + suffix);

    TaskID key = std::make_tuple(job_id, task_id);
    all_tasks.emplace(key, TaskType{/*.start=*/start,
                                    /*.end=*/end,
                                    /*.interval=*/interval});
    machine_to_intervals[machine].push_back(interval);
  }
}
```

### Java

```java
class TaskType {
  IntVar start;
  IntVar end;
  IntervalVar interval;
}
Map<List<Integer>, TaskType> allTasks = new HashMap<>();
Map<Integer, List<IntervalVar>> machineToIntervals = new HashMap<>();

for (int jobID = 0; jobID < allJobs.size(); ++jobID) {
  List<Task> job = allJobs.get(jobID);
  for (int taskID = 0; taskID < job.size(); ++taskID) {
    Task task = job.get(taskID);
    String suffix = "_" + jobID + "_" + taskID;

    TaskType taskType = new TaskType();
    taskType.start = model.newIntVar(0, horizon, "start" + suffix);
    taskType.end = model.newIntVar(0, horizon, "end" + suffix);
    taskType.interval = model.newIntervalVar(
        taskType.start, LinearExpr.constant(task.duration), taskType.end, "interval" + suffix);

    List<Integer> key = Arrays.asList(jobID, taskID);
    allTasks.put(key, taskType);
    machineToIntervals.computeIfAbsent(task.machine, (Integer k) -> new ArrayList<>());
    machineToIntervals.get(task.machine).add(taskType.interval);
  }
}
```

### C#

```c#
Dictionary<Tuple<int, int>, Tuple<IntVar, IntVar, IntervalVar>> allTasks =
    new Dictionary<Tuple<int, int>, Tuple<IntVar, IntVar, IntervalVar>>(); // (start, end, duration)
Dictionary<int, List<IntervalVar>> machineToIntervals = new Dictionary<int, List<IntervalVar>>();
for (int jobID = 0; jobID < allJobs.Count(); ++jobID)
{
    var job = allJobs[jobID];
    for (int taskID = 0; taskID < job.Count(); ++taskID)
    {
        var task = job[taskID];
        String suffix = $"_{jobID}_{taskID}";
        IntVar start = model.NewIntVar(0, horizon, "start" + suffix);
        IntVar end = model.NewIntVar(0, horizon, "end" + suffix);
        IntervalVar interval = model.NewIntervalVar(start, task.duration, end, "interval" + suffix);
        var key = Tuple.Create(jobID, taskID);
        allTasks[key] = Tuple.Create(start, end, interval);
        if (!machineToIntervals.ContainsKey(task.machine))
        {
            machineToIntervals.Add(task.machine, new List<IntervalVar>());
        }
        machineToIntervals[task.machine].Add(interval);
    }
}
```

For each job and task, the program uses the model's
`NewIntVar/new_int_var/newIntVar` method to create the variables:

- `start_var`: Start time of the task.
- `end_var`: End time of the task.

The upper bound for `start_var` and `end_var` is `horizon`, the sum of the
processing times for all tasks in all jobs.
`horizon` is sufficiently large to complete all tasks for the following reason:
if you schedule the tasks in non-overlapping time intervals (a non-optimal
solution), the total length of the schedule is exactly `horizon`. So the
duration of the optimal solution can't be any greater than `horizon`.

Next, the program uses the `NewIntervalVar/new_interval_var/newIntervalVar`
method to create an **interval variable** ---whose value is a variable time
interval --- for the task. The inputs to this method are:

- The start time of the task.
- The length of the time interval for the task.
- The end time of the task.
- The name for the interval variable.

In any solution, `end_var` minus `start_var` must equal `duration`.

### Define the constraints

The following code defines the constraints for the problem.

### Python

```python
# Create and add disjunctive constraints.
for machine in all_machines:
    model.add_no_overlap(machine_to_intervals[machine])

# Precedences inside a job.
for job_id, job in enumerate(jobs_data):
    for task_id in range(len(job) - 1):
        model.add(
            all_tasks[job_id, task_id + 1].start >= all_tasks[job_id, task_id].end
        )
```

### C++

```c++
// Create and add disjunctive constraints.
for (const auto machine : all_machines) {
  cp_model.AddNoOverlap(machine_to_intervals[machine]);
}

// Precedences inside a job.
for (int job_id = 0; job_id < jobs_data.size(); ++job_id) {
  const auto& job = jobs_data[job_id];
  for (int task_id = 0; task_id < job.size() - 1; ++task_id) {
    TaskID key = std::make_tuple(job_id, task_id);
    TaskID next_key = std::make_tuple(job_id, task_id + 1);
    cp_model.AddGreaterOrEqual(all_tasks[next_key].start, all_tasks[key].end);
  }
}
```

### Java

```java
// Create and add disjunctive constraints.
for (int machine : allMachines) {
  List<IntervalVar> list = machineToIntervals.get(machine);
  model.addNoOverlap(list);
}

// Precedences inside a job.
for (int jobID = 0; jobID < allJobs.size(); ++jobID) {
  List<Task> job = allJobs.get(jobID);
  for (int taskID = 0; taskID < job.size() - 1; ++taskID) {
    List<Integer> prevKey = Arrays.asList(jobID, taskID);
    List<Integer> nextKey = Arrays.asList(jobID, taskID + 1);
    model.addGreaterOrEqual(allTasks.get(nextKey).start, allTasks.get(prevKey).end);
  }
}
```

### C#

```c#
// Create and add disjunctive constraints.
foreach (int machine in allMachines)
{
    model.AddNoOverlap(machineToIntervals[machine]);
}

// Precedences inside a job.
for (int jobID = 0; jobID < allJobs.Count(); ++jobID)
{
    var job = allJobs[jobID];
    for (int taskID = 0; taskID < job.Count() - 1; ++taskID)
    {
        var key = Tuple.Create(jobID, taskID);
        var nextKey = Tuple.Create(jobID, taskID + 1);
        model.Add(allTasks[nextKey].Item1 >= allTasks[key].Item2);
    }
}
```

The program uses the model's `AddNoOverlap/add_no_overlap/addNoOverlap` method
to create the no overlap constraints, which prevent tasks for
the same machine from overlapping in time.

Next, the program adds the precedence constraints, which prevent
consecutive tasks for the same job from overlapping in time. For each job and
each task in the job, a linear constraint is added to specify that the end
time of a task to occur before the start time of the next task in the job.

### Define the objective

The following code defines the objective in the problem.

### Python

```python
# Makespan objective.
obj_var = model.new_int_var(0, horizon, "makespan")
model.add_max_equality(
    obj_var,
    [all_tasks[job_id, len(job) - 1].end for job_id, job in enumerate(jobs_data)],
)
model.minimize(obj_var)
```

### C++

```c++
// Makespan objective.
IntVar obj_var = cp_model.NewIntVar({0, horizon}).WithName("makespan");

std::vector<IntVar> ends;
for (int job_id = 0; job_id < jobs_data.size(); ++job_id) {
  const auto& job = jobs_data[job_id];
  TaskID key = std::make_tuple(job_id, job.size() - 1);
  ends.push_back(all_tasks[key].end);
}
cp_model.AddMaxEquality(obj_var, ends);
cp_model.Minimize(obj_var);
```

### Java

```java
// Makespan objective.
IntVar objVar = model.newIntVar(0, horizon, "makespan");
List<IntVar> ends = new ArrayList<>();
for (int jobID = 0; jobID < allJobs.size(); ++jobID) {
  List<Task> job = allJobs.get(jobID);
  List<Integer> key = Arrays.asList(jobID, job.size() - 1);
  ends.add(allTasks.get(key).end);
}
model.addMaxEquality(objVar, ends);
model.minimize(objVar);
```

### C#

```c#
// Makespan objective.
IntVar objVar = model.NewIntVar(0, horizon, "makespan");

List<IntVar> ends = new List<IntVar>();
for (int jobID = 0; jobID < allJobs.Count(); ++jobID)
{
    var job = allJobs[jobID];
    var key = Tuple.Create(jobID, job.Count() - 1);
    ends.Add(allTasks[key].Item2);
}
model.AddMaxEquality(objVar, ends);
model.Minimize(objVar);
```

This code creates an objective variable and constrains it to be the max of the
end of all jobs.

### Invoke the solver

The following code calls the solver.

### Python

```python
solver = cp_model.CpSolver()
status = solver.solve(model)
```

### C++

```c++
const CpSolverResponse response = Solve(cp_model.Build());
```

### Java

```java
CpSolver solver = new CpSolver();
CpSolverStatus status = solver.solve(model);
```

### C#

```c#
CpSolver solver = new CpSolver();
CpSolverStatus status = solver.Solve(model);
Console.WriteLine($"Solve status: {status}");
```

### Display the results

The following code displays the results, including the optimal schedule and task
intervals.

### Python

```python
if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print("Solution:")
    # Create one list of assigned tasks per machine.
    assigned_jobs = collections.defaultdict(list)
    for job_id, job in enumerate(jobs_data):
        for task_id, task in enumerate(job):
            machine = task[0]
            assigned_jobs[machine].append(
                assigned_task_type(
                    start=solver.value(all_tasks[job_id, task_id].start),
                    job=job_id,
                    index=task_id,
                    duration=task[1],
                )
            )

    # Create per machine output lines.
    output = ""
    for machine in all_machines:
        # Sort by starting time.
        assigned_jobs[machine].sort()
        sol_line_tasks = "Machine " + str(machine) + ": "
        sol_line = "           "

        for assigned_task in assigned_jobs[machine]:
            name = f"job_{assigned_task.job}_task_{assigned_task.index}"
            # add spaces to output to align columns.
            sol_line_tasks += f"{name:15}"

            start = assigned_task.start
            duration = assigned_task.duration
            sol_tmp = f"[{start},{start + duration}]"
            # add spaces to output to align columns.
            sol_line += f"{sol_tmp:15}"

        sol_line += "\n"
        sol_line_tasks += "\n"
        output += sol_line_tasks
        output += sol_line

    # Finally print the solution found.
    print(f"Optimal Schedule Length: {solver.objective_value}")
    print(output)
else:
    print("No solution found.")
```

### C++

```c++
if (response.status() == CpSolverStatus::OPTIMAL ||
    response.status() == CpSolverStatus::FEASIBLE) {
  LOG(INFO) << "Solution:";
  // create one list of assigned tasks per machine.
  struct AssignedTaskType {
    int job_id;
    int task_id;
    int64_t start;
    int64_t duration;

    bool operator<(const AssignedTaskType& rhs) const {
      return std::tie(this->start, this->duration) <
             std::tie(rhs.start, rhs.duration);
    }
  };

  std::map<int64_t, std::vector<AssignedTaskType>> assigned_jobs;
  for (int job_id = 0; job_id < jobs_data.size(); ++job_id) {
    const auto& job = jobs_data[job_id];
    for (int task_id = 0; task_id < job.size(); ++task_id) {
      const auto [machine, duration] = job[task_id];
      TaskID key = std::make_tuple(job_id, task_id);
      int64_t start = SolutionIntegerValue(response, all_tasks[key].start);
      assigned_jobs[machine].push_back(
          AssignedTaskType{/*.job_id=*/job_id,
                           /*.task_id=*/task_id,
                           /*.start=*/start,
                           /*.duration=*/duration});
    }
  }

  // Create per machine output lines.
  std::string output = "";
  for (const auto machine : all_machines) {
    // Sort by starting time.
    std::sort(assigned_jobs[machine].begin(), assigned_jobs[machine].end());
    std::string sol_line_tasks = "Machine " + std::to_string(machine) + ": ";
    std::string sol_line = "           ";

    for (const auto& assigned_task : assigned_jobs[machine]) {
      std::string name = absl::StrFormat(
          "job_%d_task_%d", assigned_task.job_id, assigned_task.task_id);
      // Add spaces to output to align columns.
      sol_line_tasks += absl::StrFormat("%-15s", name);

      int64_t start = assigned_task.start;
      int64_t duration = assigned_task.duration;
      std::string sol_tmp =
          absl::StrFormat("[%i,%i]", start, start + duration);
      // Add spaces to output to align columns.
      sol_line += absl::StrFormat("%-15s", sol_tmp);
    }
    output += sol_line_tasks + "\n";
    output += sol_line + "\n";
  }
  // Finally print the solution found.
  LOG(INFO) << "Optimal Schedule Length: " << response.objective_value();
  LOG(INFO) << "\n" << output;
} else {
  LOG(INFO) << "No solution found.";
}
```

### Java

```java
if (status == CpSolverStatus.OPTIMAL || status == CpSolverStatus.FEASIBLE) {
  class AssignedTask {
    int jobID;
    int taskID;
    int start;
    int duration;
    // Ctor
    AssignedTask(int jobID, int taskID, int start, int duration) {
      this.jobID = jobID;
      this.taskID = taskID;
      this.start = start;
      this.duration = duration;
    }
  }
  class SortTasks implements Comparator<AssignedTask> {
    @Override
    public int compare(AssignedTask a, AssignedTask b) {
      if (a.start != b.start) {
        return a.start - b.start;
      } else {
        return a.duration - b.duration;
      }
    }
  }
  System.out.println("Solution:");
  // Create one list of assigned tasks per machine.
  Map<Integer, List<AssignedTask>> assignedJobs = new HashMap<>();
  for (int jobID = 0; jobID < allJobs.size(); ++jobID) {
    List<Task> job = allJobs.get(jobID);
    for (int taskID = 0; taskID < job.size(); ++taskID) {
      Task task = job.get(taskID);
      List<Integer> key = Arrays.asList(jobID, taskID);
      AssignedTask assignedTask = new AssignedTask(
          jobID, taskID, (int) solver.value(allTasks.get(key).start), task.duration);
      assignedJobs.computeIfAbsent(task.machine, (Integer k) -> new ArrayList<>());
      assignedJobs.get(task.machine).add(assignedTask);
    }
  }

  // Create per machine output lines.
  String output = "";
  for (int machine : allMachines) {
    // Sort by starting time.
    Collections.sort(assignedJobs.get(machine), new SortTasks());
    String solLineTasks = "Machine " + machine + ": ";
    String solLine = "           ";

    for (AssignedTask assignedTask : assignedJobs.get(machine)) {
      String name = "job_" + assignedTask.jobID + "_task_" + assignedTask.taskID;
      // Add spaces to output to align columns.
      solLineTasks += String.format("%-15s", name);

      String solTmp =
          "[" + assignedTask.start + "," + (assignedTask.start + assignedTask.duration) + "]";
      // Add spaces to output to align columns.
      solLine += String.format("%-15s", solTmp);
    }
    output += solLineTasks + "%n";
    output += solLine + "%n";
  }
  System.out.printf("Optimal Schedule Length: %f%n", solver.objectiveValue());
  System.out.printf(output);
} else {
  System.out.println("No solution found.");
}
```

### C#

```c#
if (status == CpSolverStatus.Optimal || status == CpSolverStatus.Feasible)
{
    Console.WriteLine("Solution:");

    Dictionary<int, List<AssignedTask>> assignedJobs = new Dictionary<int, List<AssignedTask>>();
    for (int jobID = 0; jobID < allJobs.Count(); ++jobID)
    {
        var job = allJobs[jobID];
        for (int taskID = 0; taskID < job.Count(); ++taskID)
        {
            var task = job[taskID];
            var key = Tuple.Create(jobID, taskID);
            int start = (int)solver.Value(allTasks[key].Item1);
            if (!assignedJobs.ContainsKey(task.machine))
            {
                assignedJobs.Add(task.machine, new List<AssignedTask>());
            }
            assignedJobs[task.machine].Add(new AssignedTask(jobID, taskID, start, task.duration));
        }
    }

    // Create per machine output lines.
    String output = "";
    foreach (int machine in allMachines)
    {
        // Sort by starting time.
        assignedJobs[machine].Sort();
        String solLineTasks = $"Machine {machine}: ";
        String solLine = "           ";

        foreach (var assignedTask in assignedJobs[machine])
        {
            String name = $"job_{assignedTask.jobID}_task_{assignedTask.taskID}";
            // Add spaces to output to align columns.
            solLineTasks += $"{name,-15}";

            String solTmp = $"[{assignedTask.start},{assignedTask.start+assignedTask.duration}]";
            // Add spaces to output to align columns.
            solLine += $"{solTmp,-15}";
        }
        output += solLineTasks + "\n";
        output += solLine + "\n";
    }
    // Finally print the solution found.
    Console.WriteLine($"Optimal Schedule Length: {solver.ObjectiveValue}");
    Console.WriteLine($"\n{output}");
}
else
{
    Console.WriteLine("No solution found.");
}
```

The optimal schedule is shown below:

     Optimal Schedule Length: 11
    Machine 0: job_0_0   job_1_0
               [0,3]     [3,5]
    Machine 1: job_2_0   job_0_1   job_1_2
               [0,4]     [4,6]     [7,11]
    Machine 2: job_1_1   job_0_2   job_2_1
               [5,6]     [6,8]     [8,11]


![](https://developers.google.com/optimization/images/scheduling/schedule2.png%22%20alt=%22timeline%20of%20optimal%20jobshop%20schedule)

Eagle-eyed readers examining machine 1 might wonder why job_1_2 was scheduled at
time 7 instead of time 6. Both are valid solutions, but remember: the objective
is to minimize the makespan. Moving job_1_2 earlier wouldn't reduce the makespan
, so the two solutions are equal from the solver's perspective.

### Entire program

Finally, here is the entire program for the job shop problem.

### Python

```python
"""Minimal jobshop example."""
import collections
from ortools.sat.python import cp_model



def main() -> None:
    """Minimal jobshop problem."""
    # Data.
    jobs_data = [  # task = (machine_id, processing_time).
        [(0, 3), (1, 2), (2, 2)],  # Job0
        [(0, 2), (2, 1), (1, 4)],  # Job1
        [(1, 4), (2, 3)],  # Job2
    ]

    machines_count = 1 + max(task[0] for job in jobs_data for task in job)
    all_machines = range(machines_count)
    # Computes horizon dynamically as the sum of all durations.
    horizon = sum(task[1] for job in jobs_data for task in job)

    # Create the model.
    model = cp_model.CpModel()

    # Named tuple to store information about created variables.
    task_type = collections.namedtuple("task_type", "start end interval")
    # Named tuple to manipulate solution information.
    assigned_task_type = collections.namedtuple(
        "assigned_task_type", "start job index duration"
    )

    # Creates job intervals and add to the corresponding machine lists.
    all_tasks = {}
    machine_to_intervals = collections.defaultdict(list)

    for job_id, job in enumerate(jobs_data):
        for task_id, task in enumerate(job):
            machine, duration = task
            suffix = f"_{job_id}_{task_id}"
            start_var = model.new_int_var(0, horizon, "start" + suffix)
            end_var = model.new_int_var(0, horizon, "end" + suffix)
            interval_var = model.new_interval_var(
                start_var, duration, end_var, "interval" + suffix
            )
            all_tasks[job_id, task_id] = task_type(
                start=start_var, end=end_var, interval=interval_var
            )
            machine_to_intervals[machine].append(interval_var)

    # Create and add disjunctive constraints.
    for machine in all_machines:
        model.add_no_overlap(machine_to_intervals[machine])

    # Precedences inside a job.
    for job_id, job in enumerate(jobs_data):
        for task_id in range(len(job) - 1):
            model.add(
                all_tasks[job_id, task_id + 1].start >= all_tasks[job_id, task_id].end
            )

    # Makespan objective.
    obj_var = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(
        obj_var,
        [all_tasks[job_id, len(job) - 1].end for job_id, job in enumerate(jobs_data)],
    )
    model.minimize(obj_var)

    # Creates the solver and solve.
    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("Solution:")
        # Create one list of assigned tasks per machine.
        assigned_jobs = collections.defaultdict(list)
        for job_id, job in enumerate(jobs_data):
            for task_id, task in enumerate(job):
                machine = task[0]
                assigned_jobs[machine].append(
                    assigned_task_type(
                        start=solver.value(all_tasks[job_id, task_id].start),
                        job=job_id,
                        index=task_id,
                        duration=task[1],
                    )
                )

        # Create per machine output lines.
        output = ""
        for machine in all_machines:
            # Sort by starting time.
            assigned_jobs[machine].sort()
            sol_line_tasks = "Machine " + str(machine) + ": "
            sol_line = "           "

            for assigned_task in assigned_jobs[machine]:
                name = f"job_{assigned_task.job}_task_{assigned_task.index}"
                # add spaces to output to align columns.
                sol_line_tasks += f"{name:15}"

                start = assigned_task.start
                duration = assigned_task.duration
                sol_tmp = f"[{start},{start + duration}]"
                # add spaces to output to align columns.
                sol_line += f"{sol_tmp:15}"

            sol_line += "\n"
            sol_line_tasks += "\n"
            output += sol_line_tasks
            output += sol_line

        # Finally print the solution found.
        print(f"Optimal Schedule Length: {solver.objective_value}")
        print(output)
    else:
        print("No solution found.")

    # Statistics.
    print("\nStatistics")
    print(f"  - conflicts: {solver.num_conflicts}")
    print(f"  - branches : {solver.num_branches}")
    print(f"  - wall time: {solver.wall_time}s")


if __name__ == "__main__":
    main()
```

### C++

```c++
// Nurse scheduling problem with shift requests.
#include <stdlib.h>

#include <algorithm>
#include <cstdint>
#include <map>
#include <numeric>
#include <string>
#include <tuple>
#include <vector>

#include "absl/base/log_severity.h"
#include "absl/log/globals.h"
#include "absl/strings/str_format.h"
#include "ortools/base/init_google.h"
#include "ortools/base/logging.h"
#include "ortools/sat/cp_model.h"
#include "ortools/sat/cp_model.pb.h"
#include "ortools/sat/cp_model_solver.h"

namespace operations_research {
namespace sat {

void MinimalJobshopSat() {
  using Task = std::tuple<int64_t, int64_t>;  // (machine_id, processing_time)
  using Job = std::vector<Task>;
  std::vector<Job> jobs_data = {
      {{0, 3}, {1, 2}, {2, 2}},  // Job_0: Task_0 Task_1 Task_2
      {{0, 2}, {2, 1}, {1, 4}},  // Job_1: Task_0 Task_1 Task_2
      {{1, 4}, {2, 3}},          // Job_2: Task_0 Task_1
  };

  int64_t num_machines = 0;
  for (const auto& job : jobs_data) {
    for (const auto& [machine, _] : job) {
      num_machines = std::max(num_machines, 1 + machine);
    }
  }

  std::vector<int> all_machines(num_machines);
  std::iota(all_machines.begin(), all_machines.end(), 0);

  // Computes horizon dynamically as the sum of all durations.
  int64_t horizon = 0;
  for (const auto& job : jobs_data) {
    for (const auto& [_, time] : job) {
      horizon += time;
    }
  }

  // Creates the model.
  CpModelBuilder cp_model;

  struct TaskType {
    IntVar start;
    IntVar end;
    IntervalVar interval;
  };

  using TaskID = std::tuple<int, int>;  // (job_id, task_id)
  std::map<TaskID, TaskType> all_tasks;
  std::map<int64_t, std::vector<IntervalVar>> machine_to_intervals;
  for (int job_id = 0; job_id < jobs_data.size(); ++job_id) {
    const auto& job = jobs_data[job_id];
    for (int task_id = 0; task_id < job.size(); ++task_id) {
      const auto [machine, duration] = job[task_id];
      std::string suffix = absl::StrFormat("_%d_%d", job_id, task_id);
      IntVar start = cp_model.NewIntVar({0, horizon})
                         .WithName(std::string("start") + suffix);
      IntVar end = cp_model.NewIntVar({0, horizon})
                       .WithName(std::string("end") + suffix);
      IntervalVar interval = cp_model.NewIntervalVar(start, duration, end)
                                 .WithName(std::string("interval") + suffix);

      TaskID key = std::make_tuple(job_id, task_id);
      all_tasks.emplace(key, TaskType{/*.start=*/start,
                                      /*.end=*/end,
                                      /*.interval=*/interval});
      machine_to_intervals[machine].push_back(interval);
    }
  }

  // Create and add disjunctive constraints.
  for (const auto machine : all_machines) {
    cp_model.AddNoOverlap(machine_to_intervals[machine]);
  }

  // Precedences inside a job.
  for (int job_id = 0; job_id < jobs_data.size(); ++job_id) {
    const auto& job = jobs_data[job_id];
    for (int task_id = 0; task_id < job.size() - 1; ++task_id) {
      TaskID key = std::make_tuple(job_id, task_id);
      TaskID next_key = std::make_tuple(job_id, task_id + 1);
      cp_model.AddGreaterOrEqual(all_tasks[next_key].start, all_tasks[key].end);
    }
  }

  // Makespan objective.
  IntVar obj_var = cp_model.NewIntVar({0, horizon}).WithName("makespan");

  std::vector<IntVar> ends;
  for (int job_id = 0; job_id < jobs_data.size(); ++job_id) {
    const auto& job = jobs_data[job_id];
    TaskID key = std::make_tuple(job_id, job.size() - 1);
    ends.push_back(all_tasks[key].end);
  }
  cp_model.AddMaxEquality(obj_var, ends);
  cp_model.Minimize(obj_var);

  const CpSolverResponse response = Solve(cp_model.Build());

  if (response.status() == CpSolverStatus::OPTIMAL ||
      response.status() == CpSolverStatus::FEASIBLE) {
    LOG(INFO) << "Solution:";
    // create one list of assigned tasks per machine.
    struct AssignedTaskType {
      int job_id;
      int task_id;
      int64_t start;
      int64_t duration;

      bool operator<(const AssignedTaskType& rhs) const {
        return std::tie(this->start, this->duration) <
               std::tie(rhs.start, rhs.duration);
      }
    };

    std::map<int64_t, std::vector<AssignedTaskType>> assigned_jobs;
    for (int job_id = 0; job_id < jobs_data.size(); ++job_id) {
      const auto& job = jobs_data[job_id];
      for (int task_id = 0; task_id < job.size(); ++task_id) {
        const auto [machine, duration] = job[task_id];
        TaskID key = std::make_tuple(job_id, task_id);
        int64_t start = SolutionIntegerValue(response, all_tasks[key].start);
        assigned_jobs[machine].push_back(
            AssignedTaskType{/*.job_id=*/job_id,
                             /*.task_id=*/task_id,
                             /*.start=*/start,
                             /*.duration=*/duration});
      }
    }

    // Create per machine output lines.
    std::string output = "";
    for (const auto machine : all_machines) {
      // Sort by starting time.
      std::sort(assigned_jobs[machine].begin(), assigned_jobs[machine].end());
      std::string sol_line_tasks = "Machine " + std::to_string(machine) + ": ";
      std::string sol_line = "           ";

      for (const auto& assigned_task : assigned_jobs[machine]) {
        std::string name = absl::StrFormat(
            "job_%d_task_%d", assigned_task.job_id, assigned_task.task_id);
        // Add spaces to output to align columns.
        sol_line_tasks += absl::StrFormat("%-15s", name);

        int64_t start = assigned_task.start;
        int64_t duration = assigned_task.duration;
        std::string sol_tmp =
            absl::StrFormat("[%i,%i]", start, start + duration);
        // Add spaces to output to align columns.
        sol_line += absl::StrFormat("%-15s", sol_tmp);
      }
      output += sol_line_tasks + "\n";
      output += sol_line + "\n";
    }
    // Finally print the solution found.
    LOG(INFO) << "Optimal Schedule Length: " << response.objective_value();
    LOG(INFO) << "\n" << output;
  } else {
    LOG(INFO) << "No solution found.";
  }

  // Statistics.
  LOG(INFO) << "Statistics";
  LOG(INFO) << CpSolverResponseStats(response);
}

}  // namespace sat
}  // namespace operations_research

int main(int argc, char* argv[]) {
  InitGoogle(argv[0], &argc, &argv, true);
  absl::SetStderrThreshold(absl::LogSeverityAtLeast::kInfo);
  operations_research::sat::MinimalJobshopSat();
  return EXIT_SUCCESS;
}
```

### Java

```java
package com.google.ortools.sat.samples;
import static java.lang.Math.max;

import com.google.ortools.Loader;
import com.google.ortools.sat.CpModel;
import com.google.ortools.sat.CpSolver;
import com.google.ortools.sat.CpSolverStatus;
import com.google.ortools.sat.IntVar;
import com.google.ortools.sat.IntervalVar;
import com.google.ortools.sat.LinearExpr;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;

/** Minimal Jobshop problem. */
public class MinimalJobshopSat {
  public static void main(String[] args) {
    Loader.loadNativeLibraries();
    class Task {
      int machine;
      int duration;
      Task(int machine, int duration) {
        this.machine = machine;
        this.duration = duration;
      }
    }

    final List<List<Task>> allJobs =
        Arrays.asList(Arrays.asList(new Task(0, 3), new Task(1, 2), new Task(2, 2)), // Job0
            Arrays.asList(new Task(0, 2), new Task(2, 1), new Task(1, 4)), // Job1
            Arrays.asList(new Task(1, 4), new Task(2, 3)) // Job2
        );

    int numMachines = 1;
    for (List<Task> job : allJobs) {
      for (Task task : job) {
        numMachines = max(numMachines, 1 + task.machine);
      }
    }
    final int[] allMachines = IntStream.range(0, numMachines).toArray();

    // Computes horizon dynamically as the sum of all durations.
    int horizon = 0;
    for (List<Task> job : allJobs) {
      for (Task task : job) {
        horizon += task.duration;
      }
    }

    // Creates the model.
    CpModel model = new CpModel();

    class TaskType {
      IntVar start;
      IntVar end;
      IntervalVar interval;
    }
    Map<List<Integer>, TaskType> allTasks = new HashMap<>();
    Map<Integer, List<IntervalVar>> machineToIntervals = new HashMap<>();

    for (int jobID = 0; jobID < allJobs.size(); ++jobID) {
      List<Task> job = allJobs.get(jobID);
      for (int taskID = 0; taskID < job.size(); ++taskID) {
        Task task = job.get(taskID);
        String suffix = "_" + jobID + "_" + taskID;

        TaskType taskType = new TaskType();
        taskType.start = model.newIntVar(0, horizon, "start" + suffix);
        taskType.end = model.newIntVar(0, horizon, "end" + suffix);
        taskType.interval = model.newIntervalVar(
            taskType.start, LinearExpr.constant(task.duration), taskType.end, "interval" + suffix);

        List<Integer> key = Arrays.asList(jobID, taskID);
        allTasks.put(key, taskType);
        machineToIntervals.computeIfAbsent(task.machine, (Integer k) -> new ArrayList<>());
        machineToIntervals.get(task.machine).add(taskType.interval);
      }
    }

    // Create and add disjunctive constraints.
    for (int machine : allMachines) {
      List<IntervalVar> list = machineToIntervals.get(machine);
      model.addNoOverlap(list);
    }

    // Precedences inside a job.
    for (int jobID = 0; jobID < allJobs.size(); ++jobID) {
      List<Task> job = allJobs.get(jobID);
      for (int taskID = 0; taskID < job.size() - 1; ++taskID) {
        List<Integer> prevKey = Arrays.asList(jobID, taskID);
        List<Integer> nextKey = Arrays.asList(jobID, taskID + 1);
        model.addGreaterOrEqual(allTasks.get(nextKey).start, allTasks.get(prevKey).end);
      }
    }

    // Makespan objective.
    IntVar objVar = model.newIntVar(0, horizon, "makespan");
    List<IntVar> ends = new ArrayList<>();
    for (int jobID = 0; jobID < allJobs.size(); ++jobID) {
      List<Task> job = allJobs.get(jobID);
      List<Integer> key = Arrays.asList(jobID, job.size() - 1);
      ends.add(allTasks.get(key).end);
    }
    model.addMaxEquality(objVar, ends);
    model.minimize(objVar);

    // Creates a solver and solves the model.
    CpSolver solver = new CpSolver();
    CpSolverStatus status = solver.solve(model);

    if (status == CpSolverStatus.OPTIMAL || status == CpSolverStatus.FEASIBLE) {
      class AssignedTask {
        int jobID;
        int taskID;
        int start;
        int duration;
        // Ctor
        AssignedTask(int jobID, int taskID, int start, int duration) {
          this.jobID = jobID;
          this.taskID = taskID;
          this.start = start;
          this.duration = duration;
        }
      }
      class SortTasks implements Comparator<AssignedTask> {
        @Override
        public int compare(AssignedTask a, AssignedTask b) {
          if (a.start != b.start) {
            return a.start - b.start;
          } else {
            return a.duration - b.duration;
          }
        }
      }
      System.out.println("Solution:");
      // Create one list of assigned tasks per machine.
      Map<Integer, List<AssignedTask>> assignedJobs = new HashMap<>();
      for (int jobID = 0; jobID < allJobs.size(); ++jobID) {
        List<Task> job = allJobs.get(jobID);
        for (int taskID = 0; taskID < job.size(); ++taskID) {
          Task task = job.get(taskID);
          List<Integer> key = Arrays.asList(jobID, taskID);
          AssignedTask assignedTask = new AssignedTask(
              jobID, taskID, (int) solver.value(allTasks.get(key).start), task.duration);
          assignedJobs.computeIfAbsent(task.machine, (Integer k) -> new ArrayList<>());
          assignedJobs.get(task.machine).add(assignedTask);
        }
      }

      // Create per machine output lines.
      String output = "";
      for (int machine : allMachines) {
        // Sort by starting time.
        Collections.sort(assignedJobs.get(machine), new SortTasks());
        String solLineTasks = "Machine " + machine + ": ";
        String solLine = "           ";

        for (AssignedTask assignedTask : assignedJobs.get(machine)) {
          String name = "job_" + assignedTask.jobID + "_task_" + assignedTask.taskID;
          // Add spaces to output to align columns.
          solLineTasks += String.format("%-15s", name);

          String solTmp =
              "[" + assignedTask.start + "," + (assignedTask.start + assignedTask.duration) + "]";
          // Add spaces to output to align columns.
          solLine += String.format("%-15s", solTmp);
        }
        output += solLineTasks + "%n";
        output += solLine + "%n";
      }
      System.out.printf("Optimal Schedule Length: %f%n", solver.objectiveValue());
      System.out.printf(output);
    } else {
      System.out.println("No solution found.");
    }

    // Statistics.
    System.out.println("Statistics");
    System.out.printf("  conflicts: %d%n", solver.numConflicts());
    System.out.printf("  branches : %d%n", solver.numBranches());
    System.out.printf("  wall time: %f s%n", solver.wallTime());
  }

  private MinimalJobshopSat() {}
}
```

### C#

```c#
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using Google.OrTools.Sat;

public class ScheduleRequestsSat
{
    private class AssignedTask : IComparable
    {
        public int jobID;
        public int taskID;
        public int start;
        public int duration;

        public AssignedTask(int jobID, int taskID, int start, int duration)
        {
            this.jobID = jobID;
            this.taskID = taskID;
            this.start = start;
            this.duration = duration;
        }

        public int CompareTo(object obj)
        {
            if (obj == null)
                return 1;

            AssignedTask otherTask = obj as AssignedTask;
            if (otherTask != null)
            {
                if (this.start != otherTask.start)
                    return this.start.CompareTo(otherTask.start);
                else
                    return this.duration.CompareTo(otherTask.duration);
            }
            else
                throw new ArgumentException("Object is not a Temperature");
        }
    }

    public static void Main(String[] args)
    {
        var allJobs =
            new[] {
                new[] {
                    // job0
                    new { machine = 0, duration = 3 }, // task0
                    new { machine = 1, duration = 2 }, // task1
                    new { machine = 2, duration = 2 }, // task2
                }
                    .ToList(),
                new[] {
                    // job1
                    new { machine = 0, duration = 2 }, // task0
                    new { machine = 2, duration = 1 }, // task1
                    new { machine = 1, duration = 4 }, // task2
                }
                    .ToList(),
                new[] {
                    // job2
                    new { machine = 1, duration = 4 }, // task0
                    new { machine = 2, duration = 3 }, // task1
                }
                    .ToList(),
            }
                .ToList();

        int numMachines = 0;
        foreach (var job in allJobs)
        {
            foreach (var task in job)
            {
                numMachines = Math.Max(numMachines, 1 + task.machine);
            }
        }
        int[] allMachines = Enumerable.Range(0, numMachines).ToArray();

        // Computes horizon dynamically as the sum of all durations.
        int horizon = 0;
        foreach (var job in allJobs)
        {
            foreach (var task in job)
            {
                horizon += task.duration;
            }
        }

        // Creates the model.
        CpModel model = new CpModel();

        Dictionary<Tuple<int, int>, Tuple<IntVar, IntVar, IntervalVar>> allTasks =
            new Dictionary<Tuple<int, int>, Tuple<IntVar, IntVar, IntervalVar>>(); // (start, end, duration)
        Dictionary<int, List<IntervalVar>> machineToIntervals = new Dictionary<int, List<IntervalVar>>();
        for (int jobID = 0; jobID < allJobs.Count(); ++jobID)
        {
            var job = allJobs[jobID];
            for (int taskID = 0; taskID < job.Count(); ++taskID)
            {
                var task = job[taskID];
                String suffix = $"_{jobID}_{taskID}";
                IntVar start = model.NewIntVar(0, horizon, "start" + suffix);
                IntVar end = model.NewIntVar(0, horizon, "end" + suffix);
                IntervalVar interval = model.NewIntervalVar(start, task.duration, end, "interval" + suffix);
                var key = Tuple.Create(jobID, taskID);
                allTasks[key] = Tuple.Create(start, end, interval);
                if (!machineToIntervals.ContainsKey(task.machine))
                {
                    machineToIntervals.Add(task.machine, new List<IntervalVar>());
                }
                machineToIntervals[task.machine].Add(interval);
            }
        }

        // Create and add disjunctive constraints.
        foreach (int machine in allMachines)
        {
            model.AddNoOverlap(machineToIntervals[machine]);
        }

        // Precedences inside a job.
        for (int jobID = 0; jobID < allJobs.Count(); ++jobID)
        {
            var job = allJobs[jobID];
            for (int taskID = 0; taskID < job.Count() - 1; ++taskID)
            {
                var key = Tuple.Create(jobID, taskID);
                var nextKey = Tuple.Create(jobID, taskID + 1);
                model.Add(allTasks[nextKey].Item1 >= allTasks[key].Item2);
            }
        }

        // Makespan objective.
        IntVar objVar = model.NewIntVar(0, horizon, "makespan");

        List<IntVar> ends = new List<IntVar>();
        for (int jobID = 0; jobID < allJobs.Count(); ++jobID)
        {
            var job = allJobs[jobID];
            var key = Tuple.Create(jobID, job.Count() - 1);
            ends.Add(allTasks[key].Item2);
        }
        model.AddMaxEquality(objVar, ends);
        model.Minimize(objVar);

        // Solve
        CpSolver solver = new CpSolver();
        CpSolverStatus status = solver.Solve(model);
        Console.WriteLine($"Solve status: {status}");

        if (status == CpSolverStatus.Optimal || status == CpSolverStatus.Feasible)
        {
            Console.WriteLine("Solution:");

            Dictionary<int, List<AssignedTask>> assignedJobs = new Dictionary<int, List<AssignedTask>>();
            for (int jobID = 0; jobID < allJobs.Count(); ++jobID)
            {
                var job = allJobs[jobID];
                for (int taskID = 0; taskID < job.Count(); ++taskID)
                {
                    var task = job[taskID];
                    var key = Tuple.Create(jobID, taskID);
                    int start = (int)solver.Value(allTasks[key].Item1);
                    if (!assignedJobs.ContainsKey(task.machine))
                    {
                        assignedJobs.Add(task.machine, new List<AssignedTask>());
                    }
                    assignedJobs[task.machine].Add(new AssignedTask(jobID, taskID, start, task.duration));
                }
            }

            // Create per machine output lines.
            String output = "";
            foreach (int machine in allMachines)
            {
                // Sort by starting time.
                assignedJobs[machine].Sort();
                String solLineTasks = $"Machine {machine}: ";
                String solLine = "           ";

                foreach (var assignedTask in assignedJobs[machine])
                {
                    String name = $"job_{assignedTask.jobID}_task_{assignedTask.taskID}";
                    // Add spaces to output to align columns.
                    solLineTasks += $"{name,-15}";

                    String solTmp = $"[{assignedTask.start},{assignedTask.start+assignedTask.duration}]";
                    // Add spaces to output to align columns.
                    solLine += $"{solTmp,-15}";
                }
                output += solLineTasks + "\n";
                output += solLine + "\n";
            }
            // Finally print the solution found.
            Console.WriteLine($"Optimal Schedule Length: {solver.ObjectiveValue}");
            Console.WriteLine($"\n{output}");
        }
        else
        {
            Console.WriteLine("No solution found.");
        }

        Console.WriteLine("Statistics");
        Console.WriteLine($"  conflicts: {solver.NumConflicts()}");
        Console.WriteLine($"  branches : {solver.NumBranches()}");
        Console.WriteLine($"  wall time: {solver.WallTime()}s");
    }
}
```