import {describe, it, expect} from "vitest";
import {setupWithProviders} from "../test-utils.jsx";
import GameOverPage from "../../src/components/GameOverPage.jsx";
import {useScoreStore} from "../../src/stores/score-store.jsx";

describe('GameOverPage', () => {
    it('Should show high score', () => {
        const {getByTestId} = setupWithProviders(<GameOverPage/>);
        const element = getByTestId('text-highscore');
        expect(element).toHaveTextContent('0');
    });

    it('Should show score', () => {
        const {getByTestId} = setupWithProviders(<GameOverPage/>);
        const element = getByTestId('text-score');
        expect(element).toHaveTextContent('yourScore: 0');
    });

    it('Should show leaderboard if score is higher than 0', async () => {
        useScoreStore.setState({ score: 18 });
        const {findByTestId} = setupWithProviders(<GameOverPage/>);
        const element = await findByTestId('submit-btn');
        expect(element).toHaveTextContent("Submit");
    });

    it('Should not show leaderboard if score is 0', async () => {
        const {queryByText} = setupWithProviders(<GameOverPage/>);
        const element = queryByText('Submit');
        expect(element).toBeNull();
    });
})