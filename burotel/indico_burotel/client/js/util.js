import React from 'react';

/**
 * This function instantiates a React.Component with a set of additional passed props.
 *
 * @param {React.Component} Component - the actual component that will be parametrized
 * @param {Object|Function} extraProps - additional properties passed to the final component
 */
export function parametrize(Component, extraProps) {
    const ParametrizedComponent = ({...props}) => {
        // handle deferred prop calculation
        if (typeof extraProps === 'function') {
            extraProps = extraProps();
        }

        // extraProps override props if there is a name collision
        const {children, ...attrProps} = {...props, ...extraProps};
        return React.createElement(Component, attrProps, children);
    };
    const name = Component.displayName || Component.name;
    ParametrizedComponent.displayName = `Parametrized${name}`;
    return ParametrizedComponent;
}
