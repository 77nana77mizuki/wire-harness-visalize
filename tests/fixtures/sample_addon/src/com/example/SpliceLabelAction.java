package com.example;

import com.mentor.capital.logic.IXSplice;
import com.mentor.capital.action.IXAction;
import com.mentor.capital.action.IXActionContext;

/* Sets a label attribute on every selected splice. */
public class SpliceLabelAction implements IXAction {

    @Override
    public void execute(IXActionContext context) {
        for (IXSplice splice : context.getSelectedSplices()) {
            splice.setAttribute("SPLICE_LABEL", buildLabel(splice));
        }
    }

    private String buildLabel(IXSplice splice) {
        return "S-" + splice.getId();
    }
}
