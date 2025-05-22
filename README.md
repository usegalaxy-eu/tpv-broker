# TPV Broker

Metascheduler for TPV as Service

The TPV Broker is an API that plugs in to [TPV](https://total-perspective-vortex.readthedocs.io/en/latest/)s' [rank](https://total-perspective-vortex.readthedocs.io/en/latest/topics/concepts.html#rank) function: 
> After the matching destinations are short listed, they are ranked using a pluggable rank function. The default rank function simply sorts the destinations by tags that have the most number of preferred tags, with a penalty if preferred tags are absent. However, this default rank function can be overridden per entity, allowing a custom rank function to be defined in python code, with arbitrary logic for picking the best match from the available candidate destinations.

The API takes the list of `candidate_destinations`, i.e., destinations registered in TPV (with hardcoded resource usage limits, such as the max memory allowed for a job) which can in theory statify the job requirements, eg:
```
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

