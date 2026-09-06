package com.example;

import com.mentor.capital.logic.IXConnector;
import com.mentor.capital.logic.IXWire;
import com.mentor.capital.logic.IXSignal;
import com.mentor.capital.drc.IXDrcCheck;
import com.mentor.capital.drc.IXDrcContext;
import com.mentor.capital.option.IXOptionExpression;

/** Ground circuit design-rule check. */
public class GroundCircuitDrc implements IXDrcCheck {

    private static final String ATTR_CSA = "CONDUCTOR_CSA";
    private static final double MIN_CSA_MM2 = 0.35;

    @Override
    public void run(IXDrcContext context) {
        for (IXConnector connector : context.getConnectors()) {
            String pn = connector.getAttribute("PART_NUMBER");
            if (pn == null) {
                context.addWarning(connector, "connector has no part number");
            }
        }

        for (IXWire wire : context.getWires()) {
            // option expression governs whether this wire exists in the 100% design
            IXOptionExpression expr = wire.getOptionExpression();
            if (expr != null && expr.evaluate(context.getConfiguration())) {
                double csa = wire.getValue(ATTR_CSA);
                if (csa < MIN_CSA_MM2) {
                    context.addViolation(wire, "CSA below minimum");
                }
            }
        }
    }
}
