Tempest Coding Guide
====================

- Step 1: Read the OpenStack Style Commandments
  http://docs.openstack.org/developer/hacking/
- Step 2: Read on

Tempest Specific Commandments
------------------------------

[T101] If a test is broken because of a bug it is appropriate to skip the test until
bug has been fixed. However, the skip message should be formatted so that
Tempest's skip tracking tool can watch the bug status. The skip message should
contain the string 'Bug' immediately followed by a space. Then the bug number
should be included in the message '#' in front of the number.

Example::

  @testtools.skip("Skipped until the Bug #980688 is resolved")

- [T102] Cannot import OpenStack python clients in tempest/api tests
- [T103] tempest/tests is deprecated
- [T104] Scenario tests require a services decorator

Test Data/Configuration
-----------------------
- Assume nothing about existing test data
- Tests should be self contained (provide their own data)
- Clean up test data at the completion of each test
- Use configuration files for values that will vary by environment


Exception Handling
------------------
According to the ``The Zen of Python`` the
``Errors should never pass silently.``
Tempest usually runs in special environment (jenkins gate jobs), in every
error or failure situation we should provide as much error related
information as possible, because we usually do not have the chance to
investigate the situation after the issue happened.

In every test case the abnormal situations must be very verbosely explained,
by the exception and the log.

In most cases the very first issue is the most important information.

Try to avoid using ``try`` blocks in the test cases, both the ``except``
and ``finally`` block could replace the original exception,
when the additional operations leads to another exception.

Just letting an exception to propagate, is not bad idea in a test case,
 at all.

Try to avoid using any exception handling construct which can hide the errors
origin.

If you really need to use a ``try`` block, please ensure the original
exception at least logged.  When the exception is logged you usually need
to ``raise`` the same or a different exception anyway.

Use of ``self.addCleanup`` is often a good way to avoid having to catch
exceptions and still ensure resources are correctly cleaned up if the
test fails part way through.

Use the ``self.assert*`` methods provided by the unit test framework
 the signal failures early.

Avoid using the ``self.fail`` alone, it's stack trace will signal
 the ``self.fail`` line as the origin of the error.

Avoid constructing complex boolean expressions for assertion.
The ``self.assertTrue`` or ``self.assertFalse`` without a ``msg`` argument,
will just tell you the single boolean value, and you will not know anything
about the values used in the formula, the ``msg`` argument might be good enough
for providing more information.

Most other assert method can include more information by default.
For example ``self.assertIn`` can include the whole set.

Recommended to use testtools matcher for more tricky assertion.
`[doc] <http://testtools.readthedocs.org/en/latest/for-test-authors.html#matchers>`_

You can implement your own specific matcher as well.
`[doc] <http://testtools.readthedocs.org/en/latest/for-test-authors.html#writing-your-own-matchers>`_

If the test case fails you can see the related logs and the information
carried by the exception (exception class, backtrack and exception info).
This and the service logs are your only guide to find the root cause of flaky
issue.

Test cases are independent
--------------------------
Every ``test_method`` must be callable individually and MUST NOT depends on,
any other ``test_method`` or ``test_method`` ordering.

Test cases MAY depend on commonly initialized resources/facilities, like
credentials management, testresources and so on. These facilities, MUST be able
to work even if just one ``test_method`` selected for execution.

Service Tagging
---------------
Service tagging is used to specify which services are exercised by a particular
test method. You specify the services with the tempest.test.services decorator.
For example:

@services('compute', 'image')

Valid service tag names are the same as the list of directories in tempest.api
that have tests.

For scenario tests having a service tag is required. For the api tests service
tags are only needed if the test method makes an api call (either directly or
indirectly through another service) that differs from the parent directory
name. For example, any test that make an api call to a service other than nova
in tempest.api.compute would require a service tag for those services, however
they do not need to be tagged as compute.

Guidelines
----------
- Do not submit changesets with only testcases which are skipped as
  they will not be merged.
- Consistently check the status code of responses in testcases. The
  earlier a problem is detected the easier it is to debug, especially
  where there is complicated setup required.

Parallel Test Execution
-----------------------
Tempest by default runs its tests in parallel this creates the possibility for
interesting interactions between tests which can cause unexpected failures.
Tenant isolation provides protection from most of the potential race conditions
between tests outside the same class. But there are still a few of things to
watch out for to try to avoid issues when running your tests in parallel.

- Resources outside of a tenant scope still have the potential to conflict. This
  is a larger concern for the admin tests since most resources and actions that
  require admin privileges are outside of tenants.

- Races between methods in the same class are not a problem because
  parallelization in tempest is at the test class level, but if there is a json
  and xml version of the same test class there could still be a race between
  methods.

- The rand_name() function from tempest.common.utils.data_utils should be used
  anywhere a resource is created with a name. Static naming should be avoided
  to prevent resource conflicts.

- If the execution of a set of tests is required to be serialized then locking
  can be used to perform this. See AggregatesAdminTest in
  tempest.api.compute.admin for an example of using locking.
