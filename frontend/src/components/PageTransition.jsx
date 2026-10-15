import { cloneElement, isValidElement, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

const CLEANUP_DELAY_MS = 320;

function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function layerKey(loc) {
  return `${loc.pathname}${loc.search}`;
}

export default function PageTransition({ children }) {
  const location = useLocation();
  const prevLocationRef = useRef(location);
  const [layers, setLayers] = useState(() => [
    { loc: location, exiting: false, scrollY: 0 },
  ]);

  useLayoutEffect(() => {
    const prev = prevLocationRef.current;
    if (prev.key === location.key) return;
    prevLocationRef.current = location;

    const scrollY = window.scrollY;
    const sameView =
      prev.pathname === location.pathname && prev.search === location.search;

    if (reducedMotion() || sameView) {
      setLayers([{ loc: location, exiting: false, scrollY: 0 }]);
      window.scrollTo(0, 0);
      return;
    }

    setLayers([
      { loc: prev, exiting: true, scrollY },
      { loc: location, exiting: false, scrollY: 0 },
    ]);
    window.scrollTo(0, 0);
  }, [location]);

  useEffect(() => {
    if (!layers.some((l) => l.exiting)) return;
    if (reducedMotion()) {
      setLayers((ls) => ls.filter((l) => !l.exiting));
      return;
    }
    const timer = setTimeout(() => {
      setLayers((ls) => ls.filter((l) => !l.exiting));
    }, CLEANUP_DELAY_MS);
    return () => clearTimeout(timer);
  }, [layers]);

  return (
    <div className="route-stage">
      {layers.map((layer) => (
        <div
          key={layerKey(layer.loc)}
          className={layer.exiting ? "route-exit" : "route-enter"}
          aria-hidden={layer.exiting || undefined}
          style={
            layer.exiting
              ? { "--exit-shift": `-${layer.scrollY}px` }
              : undefined
          }
        >
          {isValidElement(children)
            ? cloneElement(children, { location: layer.loc })
            : children}
        </div>
      ))}
    </div>
  );
}
