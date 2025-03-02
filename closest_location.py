from math import cos, asin, sqrt


def distance(lat1: float, lon1: float, lat2: float, lon2: float):
    p = 0.017453292519943295
    hav = 0.5 - cos((lat2-lat1)*p)/2 + cos(lat1*p)*cos(lat2*p) * (1-cos((lon2-lon1)*p)) / 2
    return 12742 * asin(sqrt(hav))


def get_object_store(dataset_attributes):
    """Extract the object store id from the dataset attributes"""
    object_store = []
    for value in dataset_attributes.values():
        if value.object_store_id:
            object_store.append(value.object_store_id)

    if len(set(object_store)) == 1:
        object_store = [object_store[0]]

    return object_store


def closest_destination(destination, objectstores, dataset_attributes) -> float:
    """
    Calculates the minimum distance between a given destination and the object store(s).
    """
    object_store = get_object_store(dataset_attributes)

    # If there is no object store, return infinity
    if not object_store:
        return float('inf')

    d_lat, d_lon = destination['latitude'], destination['longitude']
    min_distance = float('inf')

    # Calculate distance to each object store and keep the minimum
    for object_store_id in object_store:
        object_store_info = objectstores.get(object_store_id)
        if object_store_info:
            o_lat, o_lon = object_store_info.latitude, object_store_info.longitude
            min_distance = min(min_distance, distance(o_lat, o_lon, d_lat, d_lon))

    return min_distance


def calculate_matching_score(destination: dict) -> float:
    """
    Calculate the matching score between a job and a destination
    """
    median_waiting_time = destination.get('dest_tool_median_queue_time', None)
    queue_size = destination.get('dest_queue_count', 1)
    median_running_time = destination.get('dest_tool_median_run_time', None)
    running_jobs = destination.get('dest_run_count', 1)

    # Queue matching factor (qm).
    if median_waiting_time > 0 and queue_size > 0:
        qm = 1 / (median_waiting_time * queue_size)
    else:
        qm = float('inf')

    # Compute matching factor (cm).
    if median_running_time > 0 and running_jobs > 0:
        cm = 1 / (median_running_time * running_jobs)
    else:
        cm = float('inf')

    # Final matching score
    return qm + cm


def get_sorted_destinations(job_requirements, destinations: list, objectstores, dataset_attributes) -> list:
    """
    Sorts the destinations based on the matching score and distance to the input data location.
    """
    sorted_destinations = []
    cpu_required = job_requirements.cores
    memory_required = job_requirements.mem

    # Filter out destinations that are offline
    online_destinations = [
        dest for dest in destinations if dest['dest_status'] == 'online'
    ]

    if not online_destinations:
        raise ValueError("All destinations are offline, job can't be scheduled!")

    # For each destination that is online, compute:
    # 1. the distance to the input data location
    # 2. the matching score
    for dest in online_destinations:
        dest['distance_to_data'] = closest_destination(dest, objectstores, dataset_attributes)
        dest['matching_score'] = calculate_matching_score(dest)

    # first separate out preferred destinations (those with enough cpu and ram)
    # from fallback destinations (the rest)
    preferred_destinations = []
    fallback_destinations  = []
    for dest in online_destinations:
        if dest['dest_unconsumed_cpu'] > cpu_required and dest['dest_unconsumed_mem'] > memory_required:
            preferred_destinations.append(dest)
        else:
            fallback_destinations.append(dest)

    # sort destinations by
    # - matching score (higher is better?)
    # - distance to the data (less is better)
    if preferred_destinations:
        # sort and return
        return preferred_list.sort(key=lambda x: (x['matching_score'],x['distance_to_data']))
    elif fallback_destinations:
        # sort and return
        return fallback_destinations.sort(key=lambda x: (x['matching_score'],x['distance_to_data']))
    else:
        raise ValueError("Not available destinations, job can't be scheduled!")
