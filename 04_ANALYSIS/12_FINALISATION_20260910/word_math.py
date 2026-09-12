"""Small native Word equation constructors; no thesis data or external services."""
from copy import deepcopy

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def element(name, *children):
    node = OxmlElement("m:" + name)
    for child in children:
        node.append(text(child) if isinstance(child, str) else deepcopy(child))
    return node


def text(value):
    run = OxmlElement("m:r")
    token = OxmlElement("m:t")
    token.set(qn("xml:space"), "preserve")
    token.text = str(value)
    run.append(token)
    return run


def sub(base, index):
    return element("sSub", element("e", base), element("sub", index))


def fraction(numerator, denominator):
    def parts(value):
        return value if isinstance(value, (tuple, list)) else [value]
    return element("f", element("num", *parts(numerator)), element("den", *parts(denominator)))


def summation(lower, *body):
    properties = OxmlElement("m:naryPr")
    for tag, value in [("chr", "∑"), ("limLoc", "undOvr"), ("supHide", "1")]:
        child = OxmlElement("m:" + tag)
        child.set(qn("m:val"), value)
        properties.append(child)
    return element("nary", properties, element("sub", lower), element("sup"), element("e", *body))


def display(*parts):
    properties = OxmlElement("m:oMathParaPr")
    justification = OxmlElement("m:jc")
    justification.set(qn("m:val"), "center")
    properties.append(justification)
    return element("oMathPara", properties, element("oMath", *parts))
