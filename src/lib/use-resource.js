import { useEffect, useState } from "react";
import { api, all } from "./client";

export function useResource(path, isList = false, interval = 0) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState({});
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    (isList
      ? all(path, controller.signal)
      : api(path, { signal: controller.signal })
    )
      .then((data) => {
        if (!controller.signal.aborted) setState({ path, revision, data });
      })
      .catch((error) => {
        if (!controller.signal.aborted) setState({ path, revision, error });
      });
    return () => controller.abort();
  }, [path, isList, revision]);
  useEffect(() => {
    if (!interval) return;
    const timer = setInterval(
      () => setRevision((value) => value + 1),
      interval,
    );
    return () => clearInterval(timer);
  }, [interval]);
  const current = state.path === path && state.revision === revision;
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: Boolean(path) && (!current || (!state.data && !state.error)),
    reload: () => setRevision((value) => value + 1),
  };
}
