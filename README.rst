==============
 trio-asyncio
==============

``trio-asyncio`` is a re-implementation of the ``asyncio`` mainloop on top of
Trio.

+++++++++++
 Rationale
+++++++++++

There are quite a few asyncio-compatible libraries.

On the other hand, Trio has native concepts of tasks and task cancellation.
Asyncio is based on callbacks and chaining Futures, albeit with nicer syntax,
which make handling of failures and timeouts fundamentally less reliable, esp.
in larger programs.

Thus, being able to use asyncio libraries from Trio is useful.

--------------------------------------
 Transparent vs. explicit translation
--------------------------------------

``trio_asyncio`` does not try to magically allow you to call ``await
trio_code()`` from asyncio, nor vice versa. There are multiple reasons for
this, among them

* "Explicit is better than implicit" is one of Python's core design guidelines.

* Semantic differences need to be resolved at the asyncio>trio and trio>asyncio 
  boundary. However, there is no good way to automatically find these
  boundaries, much less insert code into them.

* Even worse, a trio>asyncio>trio transition, or vice versa, would be
  invisible without traversing the call chain at every non-trivial event;
  that would impact performance unacceptably.

Therefore, an attempt to execute such a cross-domain call will result in an
irrecoverable error. You need to keep your code's ``asyncio`` and ``trio``
domains rigidly separate.

++++++++++++++++++++++++
 Principle of operation
++++++++++++++++++++++++

The core of the "normal" asyncio main loop is the repeated execution of
synchronous code that's submitted to ``call_soon`` or ``call_later``,
or as the callbacks for ``add_reader``/``add_writer``.

Everything else within the ``asyncio`` core, i.e. Futures and
``async``/``await``, is just syntactic sugar. There is no concept of a
task; while a Future can be cancelled, that in itself doesn't affect the
code responsible for fulfilling it.

``trio_asyncio`` thus implements a task which runs (its own version of) the
asyncio main loop. It also contains shim code which translates between these
concepts as transparently and correctly as possible, and it supplants a few
of the standard loop's key functions.

This works rather well: ``trio_asyncio`` consists of ~600 lines of code
(asyncio: ~8000) but has passed the complete Python 3.6 test suite.

An asyncio main loop may be interrupted and restarted at any
time, simply by repeated calls to ``loop.run_until_complete(coroutine)``.
Trio, however requires one long-running main loop. These differences are 
bridged by moving Trio operation to a separate thread that's switched to when
you use one of these calls.

+++++++
 Usage
+++++++

Importing ``trio_asyncio`` replaces the default ``asyncio`` event loop with
``trio_asyncio``'s version. Thus it's mandatory to do that import before
using any ``asyncio`` code.

----------------------
 Startup and shutdown
----------------------

.. _trio-loop:

Trio main loop
++++++++++++++

Typically, you start with a Trio program which you need to extend with
asyncio code.

* before::

    import trio

    trio.run(async_main, *args)


* after::

    import trio_asyncio
    import asyncio
    
    loop = asyncio.get_event_loop()
    loop.run_task(async_main, *args)

Equivalently, wrap your main loop in a :func:`trio_asyncio.open_loop` call ::

    async def async_main(*args):
        async with trio_asyncio.open_loop() as loop:
            …

Within ``async_main``, the asyncio mainloop is active.

Stopping
--------

The asyncio mainloop will be stopped automatically when the code within
``async with open_loop()`` exits. Trio-asyncio will will process all
outstanding callbacks and terminate. As in asyncio, callbacks which are
added during this step will be ignored.

You cannot restart the loop, nor would you want to.

Asyncio main loop
+++++++++++++++++

Well …

What you really want to do is to use a Trio main loop, and run your asyncio
code in its context. In other words, you should transform this code::

    def main():
        loop = asyncio.get_event_loop()
        loop.run_until_complete(async_main())
    
to this::

    async def trio_main():
        async with trio_asyncio.open_loop() as loop:
            await trio.run_asyncio(async_main)

    def main():
        trio.run(trio_main)
    
You don't need to pass around the ``loop`` argument since trio remembers it
in its task structure: ``asyncio.get_event_loop()`` always works while
your program is executing an ``async with open_loop():`` block.

There is no Trio equivalent to ``loop.run_forever()``. The loop terminates
when you leave the ``async with`` block; it cannot be halted or restarted.

This mode is called an "async loop" or "asynchronous loop" because it is
started from an async (Trio) context.

Compatibility mode
------------------

You still can do things "the asyncio way": the to-be-replaced code from the
previous section still works. However, behind the scenes
a separate thread executes the Trio main loop. It runs in lock-step with
the thread that calls ``loop.run_forever()`` or
``loop.run_until_complete(coro)``. Signals etc. get
delegated if possible (except for [SIGCHLD]_). Thus, there should be no
concurrency issues.

Caveat: you may still experience problems, particularly if your code (or
a library you're calling) does not expect to run in a different thread.

.. [SIGCHLD] Python requires you to register SIGCHLD handlers in the main
   thread, but doesn't run them at all when waiting for another thread.
   
   Use :func:`loop.add_child_handler`, :func:`trio.hazmat.wait_for_child`
   or :func:`trio.run_subprocess` instead.

``loop.stop()`` tells the loop to suspend itself. You can restart it
with another call to ``loop.run_forever()`` or ``loop.run_until_complete(coro)``,
just as with a regular asyncio loop.

This mode is called a "sync loop" or "synchronous loop" because it is
started and used from a traditional synchronous Python context.

If you use a sync loop in a separate thread, you *must* stop and close it
before terminating the thread. Otherwise your thread will leak resources.

.. warning::
   Compatibility mode has been added to verify that various test suites,
   most notably the one from asyncio itself, continue to work. In a
   real-world program with a long-running asyncio mainloop, you *really*
   want to use a :ref`Trio mainloop <trio-loop>` instead.

Stopping
--------

You can call ``loop.stop()``, or simply leave the ``async with`` block.

Unlike ``trio.run()``, which waits for all running tasks to complete,
stopping an asyncio loop will process all outstanding callbacks and then
terminate.

You cannot restart an async loop, not would you want to. Sync loops can of
course be re-entered by calling ``loop.run_forever()`` or
``loop.run_until_complete(coro)`` again.

---------------
 Cross-calling
---------------

Calling Trio from asyncio
+++++++++++++++++++++++++

Pass the function and any arguments to ``loop.run_trio()``. This method
returns a standard asyncio Future which you can await, add callbacks to,
or whatever.

::

    async def some_trio_code(foo):
        await trio.sleep(1)
        return foo*2
    
    future = loop.run_trio(some_trio_code, 21)
    res = await future
    assert res == 42

You can also use the ``aio2trio`` decorator::

    @aio2trio
    async def some_trio_code(self, foo):
        await trio.sleep(1)
        return foo+33

    res = await some_trio_code(9)
    assert res == 42

It is OK to call ``run_trio()``, or a decorated function or method, from a
synchronous context (e.g. a callback hook). However, you're responsible for
catching any errors – either await() the future, or use
``.add_done_callback()``.

If you want to start a task that shall be monitored by trio (i.e. an
uncaught error will propagate and terminate the loop), use
``run_trio_task()`` instead.

Calling asyncio from Trio
+++++++++++++++++++++++++

Pass the function and any arguments to ``loop.run_asyncio()``. This method
conforms to Trio's standard task semantics.

::

    async def some_asyncio_code(foo):
        await asyncio.sleep(1)
        return foo*20
    
    res = await trio.run_asyncio(some_trio_code, 21)
    assert res == 420

If you already have a coroutine you need to await, call ``loop.run_coroutine()``:

::

    async def some_asyncio_code(foo):
        await asyncio.sleep(1)
        return foo*20
    
    fut = asyncio.ensure_future(some_asyncio_code(21))
    res = await trio.run_coroutine(fut)
    assert res == 420


You can also use the ``trio2aio`` decorator::

    @trio2aio
    async def some_asyncio_code(self, foo):
        await asyncio.sleep(1)
        return foo+33

    # then, within a trio function
    res = await some_asyncio_code(9)
    assert res == 42

Multiple asyncio loops
++++++++++++++++++++++

Trio-asyncio supports running multiple concurrent asyncio loops in the same
thread. You may even nest them (if they're asynchronous, of course).

This means that you can write a trio-ish wrapper around an asyncio-using
library without regard to whether the main loop or another library also use
trio-asyncio.

You can use ``loop.autoclose(fd)`` to tell trio-asyncio to auto-close
a file descriptor when the loop terminates. This setting only applies to
file descriptors that have been submitted to a loop's ``add_reader`` or
``add_writer`` methods. As such, this method is mainly useful for servers
and should be used as supplementing, but not replacing, a ``finally:``
handler or an ``async with aclosing():`` block.

Errors and cancellations
++++++++++++++++++++++++

Errors and cancellations are propagated almost-transparently.

For errors, this is straightforward.

Cancellations are also propagated whenever possible. This means

* the code called from ``run_trio()`` is cancelled when you cancel
  the future it returns

* when the code called from ``run_trio()`` is cancelled, 
  the future it returns gets cancelled

* the future used in ``run_future()`` is cancelled when the Trio code
  calling it is stopped

* However, when the future passed to ``run_future()`` is cancelled (i.e.
  when the code inside raises ``asyncio.CancelledError``), that exception is
  passed along unchanged.

----------------
 Deferred Calls
----------------

``loop.call_soon()`` and friends work as usual.

---------
 Threads
---------

``loop.run_in_executor()`` works as usual.

There is one caveat: the executor must be either ``None`` or an instance of
``trio_asyncio.TrioExecutor``. The constructor of this class accepts one
argument: the number of workers.

------------------
 File descriptors
------------------

``add_reader`` and ``add_writer`` work as usual, if you really need them.

However, you might consider converting code using these calls to native
Trio tasks.

---------
 Signals
---------

``add_signal_handler`` works as usual.

++++++++++++++++++++++
 Hacking trio-asyncio
++++++++++++++++++++++

-----------
 Licensing
-----------

Like trio, trio-asyncio is licensed under both the MIT and Apache licenses.
Submitting patches or pull requests imply your acceptance of these licenses.

---------
 Patches
---------

are accepted gladly.

---------
 Testing
---------

As in trio, testing is done with ``pytest``.

Test coverage is close to 100%. Please keep it that way.

++++++++
 Author
++++++++

Matthias Urlichs <matthias@urlichs.de>

