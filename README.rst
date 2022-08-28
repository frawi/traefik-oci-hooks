===============
 Traefik Hooks
===============

Automatically generate Traefik configuration files when a container is started.
This enables an integration of Traefik with Podman without using the Docker socket.

Installation
============

Podman
------

By default, hooks are located in ``/etc/containers/oci/hooks.d``.
However, using this default is deprecated and instead the hooks dir should be explicitly set.
The path to the ``hooks.d`` directory can be specified with the ``--hoks-dir=PATH`` parameter.
To run the hook by default you can use the following steps:

 1. Copy the ``hooks.d`` directory to ``/etc/containers``.
 2. Edit (or create) ``/etc/containers/containers.conf`` to setup the hooks directory by default.
    Add the following setting::

    [engine]
    hooks_dir = ["/etc/containers/hooks.d"]

If you use a different location, you need to edit the ``hooks.d/taefik.json`` to point to the correct path of the ``traefik.py`` script.
With newer versions of podman, you can also add the configuration into ``/etc/containers/containers.conf.d`` instead.

Traefik
-------

The hook will generate dynamic configuration files.
The script will store the files in ``/srv/traefik/dynamic``.
Change the variable ``TRAEFIK_DYNAMIC`` in the file ``hooks.d/traefik.py`` to point to your preferred location.
These files have to be consumed by Traefik.
Traefik has to be setup to use the file provider pointed at the specified location and watch for changes.
For example::

    providers:
      file:
        directory: "/srv/traefik/dynamic/"
        watch: true


Known Limitations
=================

* The handling of networks is very basic at the moment.
  The generated Traefik configuration will point to the port exposed by the container on the local machine.
  This works for simple setups, but might not work for some advanced usages with multiple networks.
* Firewall is not handled automatically.
  The Traefik proxy must be allowed to reach the exposed ports.
* The automatic port detection is not exactly the same as with the Docker socket.
  If multiple ports are exposed, it will just use the first one it finds.
  This is not always the first one specified for the container.
  If a container exposes multiple ports, the proxied port should be explicitly specified in a label.
* This is mainly tested for an HTTP proxy.
  UDP and TCP proxy is implemented, but mostly untested.
* Debugging can be a bit tricky because the script will not prevent the container from starting when it fails.
  The script needs to call ``podman inspect``, which is not possible while the hook is running.
  Therefore, the script will ``fork`` and exit.
  The output will not be easily visible.
  Add the following line to the script to store the output for debugging::

    sys.stdout = sys.stderr = open("/tmp/traefik.log", "w")
