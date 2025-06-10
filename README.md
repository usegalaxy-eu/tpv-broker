# TPV Broker

Metascheduler for TPV as Service

The TPV Broker is an API that plugs in to [TPV](https://total-perspective-vortex.readthedocs.io/en/latest/)s' [rank](https://total-perspective-vortex.readthedocs.io/en/latest/topics/concepts.html#rank) function: 
> After the matching destinations are short listed, they are ranked using a pluggable rank function. The default rank function simply sorts the destinations by tags that have the most number of preferred tags, with a penalty if preferred tags are absent. However, this default rank function can be overridden per entity, allowing a custom rank function to be defined in python code, with arbitrary logic for picking the best match from the available candidate destinations.

The TPV Broker enables dynamic, data-aware job scheduling in Galaxy. The key components are:

1. [**Metric collection**](#1-metric-collection) from Galaxy and Pulsar using Telegraf into an InfluxDB
2. [**TPV Broker API**]() to calculate rankings of the available pulsar destinations based on the collected metrics  
3. [**TPV Rank function**]() consuming the rankings

---

## 1. Metric collection 

  - Requires: 
    - InfluxDB (via `usegalaxy_eu.influxdbserver`)
    - gxadmin (via `galaxyproject.gxadmin`) 
    - Telegraf (via `dj-wasabi.telegraf`)
  - see: https://training.galaxyproject.org/training-material/topics/admin/tutorials/monitoring/tutorial.html

### 1.1 Pulsar resource usage metrics 

- [**Ansible role**](https://github.com/usegalaxy-eu/ansible-pulsar-util) for setting up metric producers/consumers related to Pulsar and Galaxy

- **Producer mode**  
  - Installs a script on Pulsar nodes to expose HTCondor stats via AMQP.

- **Consumer mode**  
  - Installs a script on the Galaxy server that:
    - Reads messages from AMQP
    - Aggregates them
    - Feeds metrics into InfluxDB using a Telegraf job (using an exec plugin)

**Purpose:** Provides up-to-date Pulsar resource stats into InfluxDB.

---

### 1.2 Pulsar queue and - tool run time metrics 

- Install two additional Telegraf jobs on the Galaxy server that:
  - Collect: 
    - aggregated tool-to-destination queue - and run times: 
       ```shell
       gxadmin iquery destination-queue-run-time --seconds --older-than=90
       ```
    - destination queue size:
       ```shell
       gxadmin iquery queue --by destination
       ```
  - Feeds metrics into InfluxDB using Telegraf


**Purpose:** Provides up-to-date Pulsar destination queue size and tool specific timing metrics into InfluxDB.

---

## 2. TPV Broker

The TPV Broker is an API that plugs in to [TPV](https://total-perspective-vortex.readthedocs.io/en/latest/)s' [rank](https://total-perspective-vortex.readthedocs.io/en/latest/topics/concepts.html#rank) function: 
> After the matching destinations are short listed, they are ranked using a pluggable rank function. The default rank function simply sorts the destinations by tags that have the most number of preferred tags, with a penalty if preferred tags are absent. However, this default rank function can be overridden per entity, allowing a custom rank function to be defined in python code, with arbitrary logic for picking the best match from the available candidate destinations.


- Exposes a FastAPI/ASGI server (using eg nginx) with endpoints for TPV to call.
- Accepts a list of candidate destinations (e.g., Pulsar, Slurm, local), with their capacity limits.
- Queries InfluxDB for metrics (CPU/memory usage, job history, etc.).
- Applies ranking algorithms to order destinations by current load and preferred tags.
- Returns best-ranked destination(s) to TPV in Galaxy.

[**Ansible role**](https://github.com/usegalaxy-eu/ansible-tpv-broker) for deploying the TPV Broker:

  - Installs the broker API (clone, venv, dependencies).
  - Configures environment variables for connecting to InfluxDB / OAuth if needed.
  - Sets up a systemd service running the broker.

## 3. TPV Rank function

The TPV config has to be updated to call the broker through the API.

**Exampe TPV config:**

```yaml
users:
  esg_users:
    abstract: true
    params:
    scheduling:
      prefer:
        - be-pulsar
        - de-pulsar
        - cz-pulsar
        - it-pulsar
        - sp-pulsar
        - uk-pulsar
        - tr-pulsar
        - nor-pulsar
        - pl-pulsar
        - ch-pulsar
        - sl-pulsar
    rank: |
      import sys
      import requests
      import json
      import pathlib
      from ruamel.yaml import YAML
      import logging
    
      # Set up logging
      logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)                       
      log = logging.getLogger(__name__)
        
      # Load static objectstore info 
      # NOTE: currently object store info is stored in a yaml
      objectstore_loc_path = "{{ tpv_config_dir }}/object_store_locations.yml"
      dataset_attributes = helpers.get_dataset_attributes(job.input_datasets)

      yaml=YAML(typ='safe')
      objectstore_file = pathlib.Path(objectstore_loc_path)
      objectstore_dict = yaml.load(objectstore_file)

      # Format the destination data
      candidate_destinations_list = [{"id": dest.id, **dest.context} for dest in candidate_destinations if dest.context and 'latitude' in dest.context and 'longitude' in dest.context]
      log.debug(f"candidate_destinations_list: {candidate_destinations_list}")
      
      # Static job info
      if not entity.gpus:
        gpus = 0
      job_info = {"tool_id": tool.id, "mem": mem, "cores": cores, "gpus": gpus,}

      # URL of the FastAPI application
      api_url = "{{ inventory_hostname }}/{{ tpv_broker_proxy_config.location }}/process_data"

      input_data = {
        "destinations": candidate_destinations_list,
        "objectstores": objectstore_dict,
        "datasets": dataset_attributes,
        "job_info": job_info,
      }

      # Send a POST request to the API endpoint
      response = requests.post(api_url, json=input_data)

      # Check if the request was successful (status code 200)
      if response.status_code == 200:
          result = response.json()
      else:
          log.debug(f"Request failed with status code {response.status_code}: {response.text}")
          print(f"Request failed with status code {response.status_code}: {response.text}")

      log.debug(f"sorted destinations: {result}")
      # log.debug(f"cand destinations: {[dest.id for dest in candidate_destinations]}")
      # Sort the candidate destinations based on the sorted_destinations from the result
      final_destinations = sorted(
          (dest for dest in candidate_destinations if str(dest.id) in result["sorted_destinations"]),
          key=lambda obj: result["sorted_destinations"].index(str(obj.id))
      )

      final_destinations

  user01:
    inherits: esg_users
```

**Local TPV Broker testing:**

The API takes the list of `candidate_destinations`, i.e., destinations registered in TPV (with hardcoded resource usage limits, such as the max memory allowed for a job) which can in theory statify the job requirements, eg:

```yaml
destinations:
  slurm:
    runner: slurm
    max_accepted_cores: 32
    max_accepted_mem: 196
    max_accepted_gpus: 2
    max_cores: 16
    max_mem: 64
    max_gpus: 1
```
The api then ranks these destinations based on the metrics available about each of them in a deticated InfluxDB. is to allow efficiently schedule jobs from any UseGalaxy.* server to any Pulsar endpoint in the Pulsar network or a user-defined compute endpoint

1. Create a venv

   ```python
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the API locally:

   Set correct values for the environment variables to access InfluxDB in `set_env.sh`:
   ```shell
   source set_env.sh
   uvicorn main:app --reload
   ```

3. Testing the API with input data:

   1. Run some of the pytests in `tests`
   2. SwaggerUI: <http://127.0.0.1:8000/docs>

      Try out >  Fill out the request body using some of the test data, e.g.: `tests/example_request1.json`

   3. curl

      The Swagger UI can give you a curl version of your request after executing

   4. Using a python script with the requests or httpx library

      There is an example of how to do this with TPV:
      [example_tpv_config_locations_api.yml](./example_tpv_config_locations_api.yml).

      This config can be set up with a galaxy instance or by cloning the TPV repo
      (the example currently depends on an [open PR](https://github.com/galaxyproject/total-perspective-vortex/pull/108)):

      ```sh
      # Clone the remote repository
      git clone https://github.com/pauldg/total-perspective-vortex.git
      # Change into the cloned repository directory
      cd total-perspective-vortex
      # Checkout the desired remote branch
      git checkout -b location_test origin/location_test
      # Create a venv for testing
      python -m venv .venv
      source .venv/bin/activate
      pip install -r requirements_test.txt
      # Run pytest for the api
      pytest -rPv  tests/test_scenarios_locations.py::TestScenarios::test_scenario_esg_group_user_api
      ```

