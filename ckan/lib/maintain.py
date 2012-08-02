''' This module contains code that helps in maintaining the Ckan codebase. '''

import inspect
import time
import logging
import re

from pylons import c

log = logging.getLogger(__name__)


def deprecated(message=''):
    ''' This is a decorator used to mark functions as deprecated.

    It logs a warning when the function is called. If a message is
    passed it is also logged, this can be useful to indicate for example
    that a different function should be used instead.

    Additionally an exception is raised if the functions docstring does
    not contain the word `deprecated`.'''
    def decorator(fn):
        # When decorating a function check that the docstring is correct.
        if not fn.__doc__ or not re.search(r'\bdeprecated\b',
                                           fn.__doc__, re.IGNORECASE):
            raise Exception('Function %s() in module %s has been deprecated '
                            'but this is not mentioned in the docstring. '
                            'Please update the docstring for the function. '
                            'It must include the word `deprecated`.'
                            % (fn.__name__, fn.__module__))
        # Log deprecated functions
        log.info('Function %s() in module %s has been deprecated. %s'
                            % (fn.__name__, fn.__module__, message))

        def wrapped(*args, **kw):
            log.warning('Function %s() in module %s has been deprecated '
                         'and will be removed in a later release of ckan. %s'
                         % (fn.__name__, fn.__module__, message))
            return fn(*args, **kw)
        return wrapped
    return decorator

def deprecate_context_item(item_name, message=''):
    ''' Deprecate a named item in the global context object.

    It logs a warning when the item is accessed.  If a mesage is passed, it is
    also logged.  This can be useful to indicate for example that a different
    function should be used instead.

    No warnings are given when an attempt to change or delete the named item
    from the context object.

    Example usage:

    >>> c.facets = "Foobar"
    >>> deprecate_context_item('facets', 'Use `c.search_facets` instead')
    >>> print c.facets
    2012-07-12 13:27:06,294 WARNI [ckan.lib.maintain] c.facets has been deprecated [...]
    Foobar

    This function works by attaching a property to the underlying
    `pylons.util.AttribSafeContextObj` object which provides the storage of the
    context object.  ie - it adds a class-level attribute to the
    `pylons.util.AttribSafeContextObj` at runtime.
    '''

    class WrappedContextItem(object):
        ''' This is a fake object that calls the methods of the object
        contained. '''
        def __init__(self, obj, message):
            self._ckan_obj = obj
            self._ckan_message = message
        def __getattribute__(self, name):
            message = object.__getattribute__(self, '_ckan_message')
            log.warning('c.%s has been deprecated. %s', item_name, message)
            obj = object.__getattribute__(self, '_ckan_obj')
            # hack to get the actual object when needed
            if name == '_ckan_obj':
                return obj
            return getattr(obj, name)


    # store the value in a fake object
    setattr(c, item_name, WrappedContextItem(getattr(c, item_name), message))

    # we need to store the origional __getattr__ and replace with our own one
    if not hasattr(c.__class__, '__old_getattr__'):
        def fake_attr(self, name):
            obj = self.__class__.__dict__['__old_getattr__'](self, name)
            if isinstance(obj, WrappedContextItem):
                return obj._ckan_obj
            else:
                return obj
        get_attr =  getattr(c.__class__, '__getattr__')
        setattr(c.__class__, '__old_getattr__', get_attr)
        setattr(c.__class__, '__getattr__', fake_attr)

def defer_context_item(item_name, function):
    ''' Allows a function to be passed that will be appended to c as a property
    so that it is only called if actually used. '''

    assert hasattr(function, '__call__'), 'must pass a function'
    setattr(c, item_name, property(function))


def timer(params):
    ''' Decorator function for basic performance testing. It logs the time
    taken to call a function.  It can either be used as a basic decorator or an
    array of parameter names can be passed. If parameter names are passed then
    the logging will include the value of the parameter if it is passed to the
    function. '''

    if hasattr(params, '__call__'):
        # this is being used as a simple decorator
        fn = params
        fn_name = '%s.%s' % (fn.__module__, fn.__name__)
        def wrapped(*args, **kw):
            start = time.time()
            result = fn(*args, **kw)
            log.info('Timer: %s %.4f' % (fn_name, time.time() - start))
            return result
        return wrapped

    assert isinstance(params, list)

    def decorator(fn):
        # we have a list of parameter names so we want to find if the parameter
        # is a named one and if so store its position
        args_info = inspect.getargspec(fn)
        params_data = []
        for param in params:
            if param in args_info.args:
                params_data.append((param, args_info.args.index(param)))
            else:
                # it could be passed in keywords
                params_data.append((param))
        fn_name = '%s.%s' % (fn.__module__, fn.__name__)
        def wrapped(*args, **kw):
            # store parameters being used in the call that we want to record
            params = []
            for param in  params_data:
                value = None
                if param[0] in kw:
                    value = kw[param[0]]
                elif len(param) != 1 and len(args) >= param[1]:
                    value = args[param[1]]
                else:
                    continue
                params.append(u'%s=%r' % (param[0], value))
            p = ', '.join(params)
            start = time.time()
            # call the function
            result = fn(*args, **kw)
            log.info('Timer: %s %.4f %s' % (fn_name, time.time() - start, p))
            return result
        return wrapped
    return decorator