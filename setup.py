from setuptools import setup, find_packages

exec(open("trio_asyncio/version.py", encoding="utf-8").read())

LONG_DESC = """\
``trio-asyncio`` is a re-implementation of the ``asyncio`` mainloop on top of
Trio.

Rationale
=========

There are quite a few asyncio-compatible libraries.

On the other hand, Trio has native concepts of tasks and task cancellation.
Asyncio, on the other hand, is based on chaining Future objects, albeit
with nicer syntax.

Thus, being able to use asyncio libraries from Trio is useful.

Principle of operation
======================

The core of the "normal" asyncio main loop is the repeated execution of
synchronous code that's submitted to ``call_soon`` or
``add_reader``/``add_writer``.

Everything else within ``asyncio``, i.e. Futures and ``async``/``await``,
is just syntactic sugar. There is no concept of a task; while a Future can
be cancelled, that in itself doesn't affect the code responsible for
fulfilling it.

On the other hand, trio has genuine tasks with no separation between
returning a value asynchronously, and the code responsible for providing
that value.

``trio_asyncio`` implements a task which runs (its own version of) the
asyncio main loop. It also contains shim code which translates between these
concepts as transparently and correctly as possible, and it supplants a few
of the standard loop's key functions.

This works rather well: ``trio_asyncio`` consists of just ~700 lines of
code (asyncio: ~8000) but passes the complete Python 3.6 test suite with no
errors.

Author
======

Matthias Urlichs <matthias@urlichs.de>

"""

setup(
    name="trio_asyncio",
    version=__version__,
    description="A re-implementation of the asyncio mainloop on top of Trio",
    long_description=LONG_DESC,
    author="Matthias Urlichs",
    author_email="matthias@urlichs.de",
    url="https://github.com/smurfix/trio-asyncio",
    license="MIT -or- Apache License 2.0",
    packages=find_packages(),
    install_requires=[
        "trio",
    ],
    # This means, just install *everything* you see under trio/, even if it
    # doesn't look like a source file, so long as it appears in MANIFEST.in:
    include_package_data=True,
    python_requires=">=3.5",
    keywords=["async", "io", "trio", "asyncio", "trio-asyncio"],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: BSD",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: System :: Networking",
    ],
)
