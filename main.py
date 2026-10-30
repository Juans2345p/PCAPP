#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lanzador compatible: delega en :mod:`pc_app.main`.

Se mantiene ``python main.py`` como punto de entrada habitual, pero toda la
lógica vive ahora en el paquete ``pc_app`` (dominio, aplicación,
infraestructura y presentación).
"""

from __future__ import annotations

import sys

from pc_app.main import main

if __name__ == "__main__":
    sys.exit(main())
