========
Overview
========

This repository contains a set of python scripts for helping tune any Linux
system for performance and scale by leveraging the Linux perf tool and 
generate from the perf traces:

- context switch heat maps (temporal distribution of context switch events)
- KVM exit heat maps (temporam distribution of kvm entry and exit events)
- KVM exit types distribution stacked bar charts (exit type distribution per task)
- core locality heat maps (on which core does task run over time)
- task scheduler core assignment heat maps (run time % on each core per task - including IDLE time)
- task per core context switch count heat maps (how many context switches per core per task)

The capture script wraps around the Linux perf tool to capture events of
interest (such as context switches, and kvm events) and generates a much more
compact binary file to be used for analysis offline.

Heatmap Gallery
---------------

(to add sample html files with embedded Java Script - try it out for now if you're curious)

perfwhiz Workflow
------------------

.. image:: images/perfwhiz.png

Licensing
---------

perfwhiz is licensed under the Apache License, Version 2.0 (the "License").
You may not use this tool except in compliance with the License.
You may obtain a copy of the License at
`<http://www.apache.org/licenses/LICENSE-2.0>`_

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Links
-----

* Documentation: WIP 
* Source: WIP 
* Supports/Bugs: WIP 
* Mailing List: WIP 

