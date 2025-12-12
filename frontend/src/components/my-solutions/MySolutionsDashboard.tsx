"use client";

import { useState, useCallback, useEffect } from "react";
import { Box, Alert, CircularProgress, Typography } from "@mui/material";
import { fetchAPI } from "@/lib/api/client";
import {
  UserSubmissionListItem,
  UserSubmissionStats,
  UserSubmissionsResponse,
} from "@/lib/types";
import { useInfiniteScroll } from "@/lib/hooks/useInfiniteScroll";
import { StatisticsCards } from "./StatisticsCards";
import { FiltersBar } from "./FiltersBar";
import { SubmissionsList } from "./SubmissionsList";

const PAGE_SIZE = 20;

export interface Filters {
  year: string;
  etap: string;
  showErrors: boolean;
}

export function MySolutionsDashboard() {
  const [submissions, setSubmissions] = useState<UserSubmissionListItem[]>([]);
  const [stats, setStats] = useState<UserSubmissionStats | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filters, setFilters] = useState<Filters>({
    year: "",
    etap: "",
    showErrors: false,
  });

  const fetchSubmissions = useCallback(
    async (newOffset: number, append: boolean = false) => {
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          offset: newOffset.toString(),
          limit: PAGE_SIZE.toString(),
        });

        if (filters.year) params.set("year", filters.year);
        if (filters.etap) params.set("etap", filters.etap);
        if (!filters.showErrors) params.set("hide_errors", "true");

        const response = await fetchAPI<UserSubmissionsResponse>(
          `/api/my-submissions?${params.toString()}`
        );

        if (append) {
          setSubmissions((prev) => [...prev, ...response.submissions]);
        } else {
          setSubmissions(response.submissions);
          // Only update stats on first fetch (not on append)
          if (response.stats.total_submissions > 0 || newOffset === 0) {
            setStats(response.stats);
          }
        }
        setTotalCount(response.total_count);
        setHasMore(response.has_more);
        setOffset(newOffset);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Nie udało się załadować danych"
        );
      } finally {
        setIsLoading(false);
      }
    },
    [filters]
  );

  // Load initial data and when filters change
  useEffect(() => {
    setSubmissions([]);
    setOffset(0);
    setHasMore(true);
    fetchSubmissions(0, false);
  }, [filters, fetchSubmissions]);

  // Handle load more for infinite scroll
  const handleLoadMore = useCallback(() => {
    if (!isLoading && hasMore) {
      fetchSubmissions(offset + PAGE_SIZE, true);
    }
  }, [isLoading, hasMore, offset, fetchSubmissions]);

  const sentinelRef = useInfiniteScroll({
    hasMore,
    isLoading,
    onLoadMore: handleLoadMore,
  });

  const handleFilterChange = (newFilters: Filters) => {
    setFilters(newFilters);
  };

  return (
    <Box>
      {/* Statistics Cards */}
      {stats && <StatisticsCards stats={stats} />}

      {/* Filters */}
      <FiltersBar
        filters={filters}
        onFilterChange={handleFilterChange}
        totalCount={totalCount}
      />

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Submissions List */}
      <SubmissionsList
        submissions={submissions}
        isLoading={isLoading}
        sentinelRef={sentinelRef}
      />

      {/* Loading indicator */}
      {isLoading && submissions.length > 0 && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
          <CircularProgress size={32} />
        </Box>
      )}

      {/* End of list message */}
      {!hasMore && submissions.length > 0 && (
        <Typography
          variant="body2"
          color="text.secondary"
          textAlign="center"
          py={2}
        >
          To już wszystko
        </Typography>
      )}
    </Box>
  );
}
