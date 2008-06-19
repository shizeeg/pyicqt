# -*- test-case-name: atop.test.test_ifcompat -*-
# Copyright 2005 Divmod, Inc.  See LICENSE file for details

"""
ZI forward compatibility crap, to make the switch easier.

In the olden days, there was C{twisted.python.components} and it was
Good.  But times, such as they are, are a' changin'.  I, for one,
welcome our new Zope overlords.  C{twisted.python.components} is now
primarily a layer of compatibility to ease the transition of Twisted
applications from the old way, C{twisted.python.components.Interface},
to the new way, C{zope.interface.Interface}.

Before, you would say this:

    from twisted.python import components

    class IFoo(components.Interface):
        def bar(self, x, y, z):
            '''stuff here
            '''

        baz = property(doc='Quux!')

    class FooImpl:
        __implements__ = IFoo

        def bar(self, x, y, z):
            print 'yay, bar.'

        baz = 7

With Zope, though, you would have said it like this:

    from zope.interface import Attribute, Interface, implements

    class IFoo(Interface):
        def bar(x, y, z):
            '''stuff here
            '''

        baz = Attribute('Quux!')

    class FooImpl:
        implements(IFoo)

        def bar(self, x, y, z):
            print 'yay, bar.'

        baz = 7


The astute reader will notice that these two are not the same.  So,
how do you write an application that works with either Twisted 1.3
(and hence the old way of doing things) as well as Twisted 2.0 (and
all of its shiny new glory)?  C{twisted.python.components} gives you
backwards compatibility, so old programs work with new versions of
Twisted, but you don't want to write new programs with the backwards
comaptibility layer: you want to write new programs with the new
shinies.  This module provides assistance for doing just that, but in
a way which will still work with Twisted 1.3.  So what you do now is
this:

    from atop.ifcompat import Attribute, Interface, implements, \\
                              backwardsCompatImplements

    class IFoo(Interface):
        def bar(x, y, z):
            '''stuff here
            '''

        baz = Attribute('Quux!')

    class FooImpl:
        implements(IFoo)

        def bar(self, x, y, z):
            print 'yay, bar.'

        baz = 7
    backwardsCompatImplements(FooImpl)

Code written thusly will take advantage of zope.interface directly
when it is reasonable to do so, and use Twisted's compatibility layer
in other circumstances.  At some distant future point, when
compatibility with Twisted 1.3 is no longer a requirement, you can
just change your imports to get things directly from zope.interface
rather than atop.ifcompat.
"""


try:
    from twisted.python.components import backwardsCompatImplements, getAdapterFactory
except ImportError:
    usingZI = False
else:
    usingZI = True
    from zope.interface import implements, Attribute, Interface,\
        providedBy, directlyProvides, classProvides, classImplements,\
        implementsOnly

    def isOrExtends(I, J):
        return I.isOrExtends(J)

    CannotAdapt = TypeError

if not usingZI:
    import types
    import inspect
    from twisted.python.components import Interface, CannotAdapt, getInterfaces
    from twisted.python.components import getAdapterClass as getAdapterFactory
    _IMPLS = '__setup_implements__'
    _PROVS = '__setup_provides__'
    _ONLY = '__implements_only__'
    def backwardsCompatImplements(X):
        for setupattr in (_IMPLS, _PROVS):
            realattr = setupattr.replace('setup_','')
            i = getattr(X, setupattr, (ITwistedHack,))
            try:
                delattr(X, setupattr)
            except AttributeError:
                pass
            L = list(i)
            if setupattr != _PROVS and not getattr(X, _ONLY, None):                
                    for base in X.__bases__:
                        baseimpls = getattr(base, realattr, ())
                        if not isinstance(baseimpls, tuple):
                            baseimpls = (baseimpls,)
                        L.extend(baseimpls)
            setattr(X, realattr, tuple(L))

    def implements(*ifaces):
        ifaces = list(ifaces)
        for iface in ifaces:
            if issubclass(iface, Interface):
                break
        else:
            ifaces.append(ITwistedHack)
        locs = inspect.currentframe().f_back.f_locals
        locs[_IMPLS] = locs.get(_IMPLS, ()) + tuple(ifaces)
    
    def implementsOnly(*ifaces):
        ifaces = list(ifaces)
        for iface in ifaces:
            if issubclass(iface, Interface):
                break
        else:
            ifaces.append(ITwistedHack)
        locs = inspect.currentframe().f_back.f_locals
        locs[_IMPLS] = tuple(ifaces)
        locs[_ONLY] = True
    def Attribute(doc):
        return property(doc=doc)

    def providedBy(obj):
        """ Hi!  I'm Troy McLure, you might remember me from such films as 'Don't Use
        Twisted.Python.Components', and 'Seriously, Don't Use
        Twisted.Python.Components, You Jackass'.  This function simulates Zope
        Interface's providedBy on a _very_ rudimentary level.  It might return
        stuff in a totally different order than ZI, but execution/adaptation
        order is one of those things which, if it is important to your
        application, you need to be using zope.interface directly anyway and
        this flimsy compatibility layer won't be enough.  """
        oclass = getattr(obj, '__class__',
                         types.ClassType)
        implementedByClass = list(getInterfaces(oclass))
        providedByClassT = getattr(oclass, '__provides__', ())
        providedByMeT = getattr(obj, '__provides__', ())
        if providedByMeT is providedByClassT:
            providedByMe = []
        else:
            providedByMe = list(providedByMeT)
        for x in implementedByClass + providedByMe:
            if x is not ITwistedHack:
                yield x

    def _itDirectlyProvides(it, interfaces):
        it.setdefault(_PROVS,[]).extend(interfaces)

    def _horribleGetComponent(klass, interface, registry=None, default=None):
        """Hi, I'm Troy ... etc.  See providedBy.

        Using classProvides makes semantics differ in horrible ways - don't
        use it.
        """
        if interface in klass.__provides__:
            return klass
        return default

#     def directlyProvides(o, *interfaces):
        # # XXX doesn't take into account inheritance, blah
#         _itDirectlyProvides(vars(o), interfaces)
#         if isinstance(o, (types.ClassType, type)):
#             vars(o)['getComponent'] = classmethod(_horribleGetComponent)
#         else:
#             def boundGetComponent(*a, **kw):
#                 return _horribleGetComponent(o, *a, **kw)
#             vars(o)['getComponent'] = boundGetComponent

    def classProvides(*interfaces):
        locs = inspect.currentframe().f_back.f_locals
        _itDirectlyProvides(locs, interfaces)
        locs['getComponent'] = classmethod(_horribleGetComponent)


    def classImplements(cls, *interfaces):
        cls.__implements__ = getattr(cls, '__implements__', ()) + interfaces


    def isOrExtends(I, J):
        return I == J # interface inheritance is NOT supported.

class ITwistedHack(Interface):
    """
    This interface is a workaround for certain implementation problems with
    the interfaces system in Twisted 1.3.
    """

__all__ = ['Interface', 'Attribute', 'backwardsCompatImplements',
           'implements', 'providedBy', 'classProvides', 'classImplements',
           'getAdapterFactory', 'CannotAdapt', 'isOrExtends', 'ITwistedHack']
