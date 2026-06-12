#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Actions related to listing and running RESTful upload services.

Normally, RESTful uploads (Weather Underground, CWOP, PWSWeather, etc.) happen
only when the WeeWX engine receives a new archive record. These actions allow a
RESTful upload to be forced manually, outside of the engine's scheduler.
"""

import logging
import socket
import sys

import weewx.engine
import weewx.manager
import weewx.restx
import weeutil.weeutil
from weeutil.weeutil import bcolors, timestamp_to_string

log = logging.getLogger('weectl-rest')


def list_rest(config_dict):
    """List all configured RESTful services, along with whether they are enabled."""

    # Instantiate a dummy engine. This loads (and starts) all the configured services,
    # including the RESTful ones.
    engine = weewx.engine.DummyEngine(config_dict)
    try:
        service_map = _build_service_map(engine, config_dict)

        if not service_map:
            print("No RESTful services are configured.")
            return

        # Print a header
        print(f"\n{bcolors.BOLD}{'Service':<20} {'Enabled':^8}  {'Class'}{bcolors.ENDC}")

        for svc_path, name, inst in service_map:
            enabled = _is_enabled(inst)
            print(f"{name:<20} {'Y' if enabled else 'N':^8}  {svc_path}")
    finally:
        engine.shutDown()


def run_rest(config_dict, services=None):
    """Force an upload to one or more RESTful services.

    Args:
        config_dict (dict): The configuration dictionary.
        services (list[str]|None): The names of the services to upload to. If None or
            empty, all enabled RESTful services will be uploaded to.
    """

    # Use a sane default socket timeout, the same as 'weectl report run' does.
    socket.setdefaulttimeout(10)

    # Instantiate a dummy engine. This loads (and starts) all the configured services,
    # including the RESTful ones.
    engine = weewx.engine.DummyEngine(config_dict)
    try:
        service_map = _build_service_map(engine, config_dict)

        # Figure out which services the user asked for.
        if services:
            # Build a set of all the names a service can be matched by (case-insensitive).
            known = set()
            for svc_path, name, _inst in service_map:
                known.add(name.lower())
                known.add(svc_path.split('.')[-1].lower())
            # Warn about any names that don't match a configured service.
            for requested in services:
                if requested.lower() not in known:
                    print(f"Unknown RESTful service: '{requested}'. "
                          f"Use 'weectl rest list' to see configured services.",
                          file=sys.stderr)
            wanted = {s.lower() for s in services}
            selected = [t for t in service_map
                        if t[1].lower() in wanted
                        or t[0].split('.')[-1].lower() in wanted]
        else:
            selected = service_map

        if not selected:
            print("No matching RESTful services to run.")
            return

        # Retrieve the most recent archive record from the database. This is the record
        # that will be uploaded.
        try:
            binding = config_dict['StdArchive']['data_binding']
        except KeyError:
            binding = 'wx_binding'

        with weewx.manager.DBBinder(config_dict) as db_binder:
            db_manager = db_binder.get_manager(binding)
            ts = db_manager.lastGoodStamp()
            record = db_manager.getRecord(ts) if ts else None

        if record is None:
            print("No archive record is available to upload.", file=sys.stderr)
            return

        print(f"Uploading record for {timestamp_to_string(record['dateTime'])}")

        for svc_path, name, inst in selected:
            if not _is_enabled(inst):
                print(f"{name}: not enabled; skipping.")
                continue
            _force_post(name, inst, record)
    finally:
        engine.shutDown()

    print("Done.")


def _build_service_map(engine, config_dict):
    """Build a list describing the configured RESTful services.

    Returns:
        list[tuple]: A list of 3-way tuples (svc_path, name, instance), where
            'svc_path' is the fully-qualified class path from the configuration file,
            'name' is a short, user-friendly name, and 'instance' is the loaded service
            object (or None if it could not be loaded).
    """
    # Retrieve the list of configured RESTful services. ConfigObj parses a single entry
    # (no trailing comma) as a string, so coerce to a list.
    services = config_dict['Engine']['Services'].get('restful_services', [])
    if not isinstance(services, list):
        services = [services]

    service_map = []
    for svc_path in services:
        if not svc_path:
            continue
        # Find the loaded instance whose class matches this configuration entry.
        inst = None
        try:
            klass = weeutil.weeutil.get_object(svc_path)
        except Exception:
            klass = None
        if klass is not None:
            for obj in engine.service_obj:
                if type(obj) is klass:
                    inst = obj
                    break
        service_map.append((svc_path, _short_name(svc_path), inst))

    return service_map


def _short_name(svc_path):
    """Derive a short, user-friendly name from a service class path.

    For example, 'weewx.restx.StdWunderground' becomes 'Wunderground'.
    """
    cls = svc_path.split('.')[-1]
    if cls.startswith('Std'):
        cls = cls[3:]
    return cls


def _is_enabled(inst):
    """A RESTful service is considered enabled if it was loaded and started a thread."""
    return inst is not None and (hasattr(inst, 'archive_thread')
                                 or hasattr(inst, 'loop_thread'))


def _force_post(name, inst, record):
    """Force a single record to be posted to a RESTful service.

    The post is done by calling the posting thread's process_record() directly. This
    bypasses the normal skip_this_post() checks (the 'stale' and 'post_interval'
    gates), so the upload happens regardless of when the last upload occurred.
    """
    thread = inst.archive_thread

    try:
        if thread.manager_dict is not None:
            with weewx.manager.open_manager(thread.manager_dict) as dbmanager:
                thread.process_record(record, dbmanager)
        else:
            thread.process_record(record, None)
    except weewx.restx.AbortedPost as e:
        print(f"{name}: post skipped: {e}")
    except weewx.restx.BadLogin as e:
        print(f"{name}: bad login: {e}", file=sys.stderr)
    except weewx.restx.FailedPost as e:
        print(f"{name}: upload FAILED: {e}", file=sys.stderr)
    except Exception as e:
        print(f"{name}: upload error: {e}", file=sys.stderr)
        log.error("rest run: unexpected error posting to %s: %s", name, e)
    else:
        print(f"{name}: upload successful.")
