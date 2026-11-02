import { useQuery } from "@tanstack/react-query";

import { catalogue } from "../api/endpoints";

const HOUR = 60 * 60 * 1000;

export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: catalogue.categories, staleTime: HOUR });
}

export function useCategory(slug) {
  return useQuery({
    queryKey: ["category", slug],
    queryFn: () => catalogue.category(slug),
    staleTime: HOUR,
    enabled: Boolean(slug),
  });
}

export function useLocationTree() {
  return useQuery({ queryKey: ["location-tree"], queryFn: catalogue.locationTree, staleTime: HOUR });
}

export function useAllServices() {
  return useQuery({
    queryKey: ["services", "all"],
    queryFn: () => catalogue.services({ page_size: 100 }),
    staleTime: HOUR,
    select: (data) => data.results,
  });
}

export function matchServices(services, term) {
  const query = term.trim().toLowerCase();
  if (!query) return services ?? [];

  const words = query.split(/\s+/).filter(Boolean);
  return (services ?? [])
    .map((service) => {
      const name = service.name.toLowerCase();
      const haystack = `${name} ${service.categoryName ?? ""} ${service.searchTerms ?? ""}`.toLowerCase();
      if (!words.every((w) => haystack.includes(w))) return null;
      const rank = name.startsWith(query) ? 0 : name.includes(query) ? 1 : 2;
      return { service, rank };
    })
    .filter(Boolean)
    .sort((a, b) => a.rank - b.rank || a.service.name.localeCompare(b.service.name))
    .map((s) => s.service);
}

export function useServiceSearch(term) {
  const { data: services, isLoading } = useAllServices();

  if (!term.trim()) return { matches: [], isLoading, isEmpty: false };

  const matches = matchServices(services, term);
  return {
    matches,
    isLoading,
    isEmpty: !isLoading && matches.length === 0,
  };
}

export function flattenAreas(tree) {
  const rows = [];
  (tree ?? []).forEach((city) => {
    city.children.forEach((thana) => {
      rows.push({ id: thana.id, label: thana.name, level: "thana", thanaName: thana.name });
      thana.children.forEach((area) => {
        rows.push({ id: area.id, label: `${area.name}, ${thana.name}`, level: "area", thanaName: thana.name });
      });
    });
  });
  return rows;
}
